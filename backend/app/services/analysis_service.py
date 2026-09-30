"""The pipeline's spine: quality -> ROI -> halo -> spreading -> features -> ensemble ->
calibration -> uncertainty -> SHAP -> decision message -> AnalysisResult.

This is the one place that decides what gets returned to the client, so the medical-safety
framing (research_classification, not diagnosis; always-present disclaimer; lab-confirmation
recommendation) is enforced here structurally rather than left to each caller.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging

import cv2
import numpy as np

from app.config import settings
from app.feature_engineering.feature_vector import build_feature_vector, feature_dict_to_row
from app.image_processing.halo_detection import detect_halo
from app.image_processing.quality import assess_quality
from app.image_processing.roi_detection import ROI, detect_sample_region
from app.models.registry import registry
from app.schemas.analysis import (
    AnalysisResult,
    ClassificationSchema,
    DecisionSupportSchema,
    ExplainabilitySchema,
    HaloSchema,
    QualitySchema,
    SpreadingSchema,
    VisualizationsSchema,
)
from app.services import storage_service
from app.services.visualization_service import (
    draw_ring_overlay,
    plot_feature_importance,
    plot_probability_distribution,
    plot_radial_intensity,
)
from app.spreading_analysis.spreading import compute_spreading_profile
from app.utils.ids import new_analysis_id

logger = logging.getLogger(__name__)

_LABEL_DISPLAY = {
    "csf_like": "CSF-like",
    "saline_like": "saline-like",
    "saliva_like": "saliva-like",
    "other": "an atypical/unclassified",
}


def load_image_from_bytes(data: bytes) -> np.ndarray:
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image — unsupported or corrupt file.")
    return image


def build_decision_support(status: str, label: str | None, uncertain: bool | None) -> DecisionSupportSchema:
    if status == "RECAPTURE_NEEDED":
        return DecisionSupportSchema(
            message="Image quality is insufficient for analysis. Please recapture with "
                    "better lighting/focus and try again.",
            recommend_lab_confirmation=False,
        )
    if status == "NO_HALO_DETECTED":
        return DecisionSupportSchema(
            message="No halo/double-ring pattern could be detected in this sample. This "
                    "does not exclude a CSF leak — the halo sign can be absent even when "
                    "CSF is present (e.g. insufficient fluid:blood mixture).",
            recommend_lab_confirmation=True,
        )

    display = _LABEL_DISPLAY.get(label or "other", "an atypical/unclassified")
    if uncertain:
        message = (
            f"Result is UNCERTAIN. The pattern shows some resemblance to a {display} "
            "pattern, but model confidence/agreement is too low for a reliable research "
            "classification. Additional laboratory testing is recommended."
        )
    else:
        message = (
            f"Pattern is compatible with a {display} halo pattern. Image analysis alone "
            "cannot confirm or exclude CSF — this is a research decision-support result, "
            "not a diagnosis."
        )
    recommend_lab = bool(uncertain) or label == "csf_like"
    return DecisionSupportSchema(message=message, recommend_lab_confirmation=recommend_lab)


def run_full_analysis(image_bytes: bytes, manual_roi: ROI | None = None) -> AnalysisResult:
    analysis_id = new_analysis_id()
    timestamp = _dt.datetime.now(_dt.timezone.utc).isoformat()

    image_bgr = load_image_from_bytes(image_bytes)
    quality = assess_quality(image_bgr)
    quality_schema = QualitySchema(status=quality.status, score=quality.score, reasons=quality.reasons)

    if quality.status == "POOR":
        result = AnalysisResult(
            analysis_id=analysis_id, timestamp=timestamp, quality=quality_schema,
            decision_support=build_decision_support("RECAPTURE_NEEDED", None, None),
            status="RECAPTURE_NEEDED",
        )
        _persist(result)
        return result

    roi = detect_sample_region(image_bgr, manual_roi=manual_roi)
    halo = detect_halo(image_bgr, roi)
    halo_schema = HaloSchema(
        detected=halo.detected, center_x=halo.center_x, center_y=halo.center_y,
        inner_radius=halo.inner_radius, outer_radius=halo.outer_radius, halo_width=halo.halo_width,
        circularity=halo.circularity, symmetry_score=halo.symmetry_score, confidence=halo.confidence,
        messages=halo.messages,
    )

    if not halo.detected:
        result = AnalysisResult(
            analysis_id=analysis_id, timestamp=timestamp, quality=quality_schema, halo=halo_schema,
            decision_support=build_decision_support("NO_HALO_DETECTED", None, None),
            status="NO_HALO_DETECTED",
        )
        _persist(result)
        return result

    spreading = compute_spreading_profile(halo, roi)
    spreading_schema = SpreadingSchema(**spreading.__dict__)

    features = build_feature_vector(image_bgr, roi, halo, spreading)
    x_row = np.array(feature_dict_to_row(features), dtype=np.float64)

    classification_schema: ClassificationSchema | None = None
    explainability_schema: ExplainabilitySchema | None = None
    visualizations_schema: VisualizationsSchema | None = None
    label = None
    uncertain = None

    if registry.loaded:
        outcome = registry.predict(x_row)
        label = outcome.ensemble.predicted_label
        uncertain = outcome.uncertainty.is_uncertain
        classification_schema = ClassificationSchema(
            research_classification=label,
            confidence=outcome.ensemble.confidence,
            class_probabilities=outcome.ensemble.class_probabilities,
            uncertain=uncertain,
            disagreement=outcome.ensemble.disagreement,
            model_version=settings.model_version,
        )
        explainability_schema = ExplainabilitySchema(top_features=outcome.top_features)
        visualizations_schema = VisualizationsSchema(
            overlay_png_base64=draw_ring_overlay(image_bgr, roi, halo),
            radial_profile_png_base64=plot_radial_intensity(halo.radial_profile, halo.inner_radius, halo.outer_radius),
            probability_chart_png_base64=plot_probability_distribution(outcome.ensemble.class_probabilities),
            feature_importance_png_base64=plot_feature_importance(outcome.top_features),
        )
    else:
        visualizations_schema = VisualizationsSchema(
            overlay_png_base64=draw_ring_overlay(image_bgr, roi, halo),
            radial_profile_png_base64=plot_radial_intensity(halo.radial_profile, halo.inner_radius, halo.outer_radius),
        )
        logger.warning("Model not loaded — returning CV/feature results without classification.")

    result = AnalysisResult(
        analysis_id=analysis_id, timestamp=timestamp, quality=quality_schema, halo=halo_schema,
        spreading=spreading_schema, classification=classification_schema,
        explainability=explainability_schema, visualizations=visualizations_schema,
        decision_support=build_decision_support("OK", label, uncertain),
        status="OK",
    )
    _persist(result)
    return result


def _persist(result: AnalysisResult) -> None:
    classification = result.classification
    storage_service.save_analysis(
        analysis_id=result.analysis_id,
        timestamp=result.timestamp,
        quality_status=result.quality.status,
        research_classification=classification.research_classification if classification else None,
        confidence=classification.confidence if classification else None,
        uncertain=classification.uncertain if classification else None,
        thumbnail_path=None,
        result_json=json.dumps(result.model_dump()),
    )
