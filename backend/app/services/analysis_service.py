"""The pipeline's spine.

`analyze_frame` runs one image through quality -> ROI -> halo -> spreading -> features ->
ensemble/calibration/uncertainty/SHAP. `assemble_result` turns a frame (plus, for video, an
aggregate over many frames) into the API response. Still images and video frames share
both, so they can never drift apart.

The medical-safety framing (research_classification, never "diagnosis"; disclaimer always
present; lab confirmation recommended for CSF-like or uncertain results) is enforced here.
"""
from __future__ import annotations

import datetime as _dt
import logging
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.config import settings
from app.feature_engineering.feature_vector import build_feature_vector, feature_dict_to_row
from app.image_processing.halo_detection import HaloDetectionResult, detect_halo
from app.image_processing.preprocessing import resize_max_dimension
from app.image_processing.quality import QualityAssessment, assess_quality
from app.image_processing.roi_detection import ROI, detect_sample_region
from app.image_processing.sample_validation import NotASampleError, validate_sample
from app.models.registry import PredictionOutcome, registry
from app.schemas.analysis import (
    AnalysisResult,
    ClassificationSchema,
    ComparisonSchema,
    DecisionSupportSchema,
    ExplainabilitySchema,
    HaloSchema,
    ModelCardSchema,
    QualitySchema,
    SpreadingSchema,
    VideoSchema,
    VisualizationsSchema,
)
from app.services import comparison_service, storage_service
from app.services.visualization_service import (
    LABEL_DISPLAY,
    draw_ring_overlay,
    encode_jpeg,
    plot_comparison_radar,
    plot_feature_importance,
    plot_probability_distribution,
    plot_radial_intensity,
)
from app.spreading_analysis.spreading import SpreadingProfile, compute_spreading_profile
from app.utils.ids import new_analysis_id

logger = logging.getLogger(__name__)


@dataclass
class FrameAnalysis:
    image_bgr: np.ndarray
    quality: QualityAssessment
    roi: ROI | None = None
    halo: HaloDetectionResult | None = None
    spreading: SpreadingProfile | None = None
    features: dict | None = None
    outcome: PredictionOutcome | None = None

    @property
    def status(self) -> str:
        if self.quality.status == "POOR":
            return "RECAPTURE_NEEDED"
        if self.halo is None or not self.halo.detected:
            return "NO_HALO_DETECTED"
        return "OK"


@dataclass
class Aggregate:
    """Final classification when it comes from more than one frame (video)."""
    class_probabilities: dict[str, float]
    label: str
    confidence: float
    disagreement: float
    uncertain: bool
    extra_reasons: list[str] = field(default_factory=list)


def load_image_from_bytes(data: bytes) -> np.ndarray:
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)  # applies EXIF orientation
    if image is None:
        raise ValueError("Could not decode image — unsupported or corrupt file.")
    return resize_max_dimension(image, settings.max_analysis_dimension)[0]


def analyze_frame(image_bgr: np.ndarray, manual_roi: ROI | None = None) -> FrameAnalysis:
    image_bgr = resize_max_dimension(image_bgr, settings.max_analysis_dimension)[0]
    frame = FrameAnalysis(image_bgr=image_bgr, quality=assess_quality(image_bgr))
    if frame.quality.status == "POOR":
        return frame
    frame.roi = detect_sample_region(image_bgr, manual_roi=manual_roi)
    frame.halo = detect_halo(image_bgr, frame.roi)
    if not frame.halo.detected:
        return frame
    frame.spreading = compute_spreading_profile(frame.halo, frame.roi)
    frame.features = build_feature_vector(image_bgr, frame.roi, frame.halo, frame.spreading)
    if registry.loaded:
        x_row = np.array(feature_dict_to_row(frame.features), dtype=np.float64)
        frame.outcome = registry.predict(x_row)
    return frame


def model_card() -> ModelCardSchema | None:
    if not registry.loaded:
        return None
    metrics = registry.metadata.get("metrics") or {}
    sensitivity = {}
    cm, labels = metrics.get("confusion_matrix"), metrics.get("confusion_matrix_labels")
    if cm and labels:
        for i, label in enumerate(labels):
            row_total = sum(cm[i])
            if row_total:
                sensitivity[label] = round(cm[i][i] / row_total, 4)
    return ModelCardSchema(
        model_version=registry.metadata.get("model_version", settings.model_version),
        test_accuracy=metrics.get("accuracy"), macro_f1=metrics.get("f1_macro"),
        per_class_sensitivity=sensitivity, n_test_samples=metrics.get("n_test_samples"),
        trained_on=registry.metadata.get("trained_on"),
    )


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
    display = LABEL_DISPLAY.get(label or "other", "an atypical/unclassified")
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


def assemble_result(
    frame: FrameAnalysis, *, input_type: str, started: float, patient_code: str | None = None,
    aggregate: Aggregate | None = None, video: VideoSchema | None = None,
    frame_timeline_png: str | None = None,
) -> AnalysisResult:
    status = frame.status
    if aggregate is not None:
        status = "OK"
    quality = QualitySchema(status=frame.quality.status, score=frame.quality.score, reasons=frame.quality.reasons)
    halo_schema = spreading_schema = classification = explainability = comparison = None
    visualizations = VisualizationsSchema(source_image_jpeg_base64=encode_jpeg(frame.image_bgr),
                                          frame_timeline_png_base64=frame_timeline_png)
    label = uncertain = None

    if frame.halo is not None:
        h = frame.halo
        halo_schema = HaloSchema(
            detected=h.detected, center_x=h.center_x, center_y=h.center_y, inner_radius=h.inner_radius,
            outer_radius=h.outer_radius, halo_width=h.halo_width, circularity=h.circularity,
            symmetry_score=h.symmetry_score, confidence=h.confidence, messages=h.messages,
        )
        visualizations.overlay_png_base64 = draw_ring_overlay(frame.image_bgr, frame.roi, h)
        visualizations.radial_profile_png_base64 = plot_radial_intensity(h.radial_profile, h.inner_radius, h.outer_radius)

    if frame.spreading is not None:
        spreading_schema = SpreadingSchema(**frame.spreading.__dict__)

    if frame.outcome is not None:
        o = frame.outcome
        if aggregate is None:
            aggregate = Aggregate(
                class_probabilities=o.ensemble.class_probabilities, label=o.ensemble.predicted_label,
                confidence=o.ensemble.confidence, disagreement=o.ensemble.disagreement,
                uncertain=o.uncertainty.is_uncertain,
            )
        label, uncertain = aggregate.label, aggregate.uncertain
        classification = ClassificationSchema(
            research_classification=label, confidence=round(aggregate.confidence, 4),
            class_probabilities={k: round(v, 4) for k, v in aggregate.class_probabilities.items()},
            uncertain=uncertain, disagreement=round(aggregate.disagreement, 4),
            model_version=settings.model_version,
        )
        explainability = ExplainabilitySchema(top_features=o.top_features)
        visualizations.probability_chart_png_base64 = plot_probability_distribution(aggregate.class_probabilities)
        visualizations.feature_importance_png_base64 = plot_feature_importance(o.top_features)

        profiles = registry.metadata.get("class_profiles") or {}
        comp = comparison_service.compare(frame.features, profiles)
        if comp:
            comparison = ComparisonSchema(**comp)
            visualizations.comparison_radar_png_base64 = plot_comparison_radar(
                comp["features"], comp["feature_labels"], comp["sample_values"], profiles, highlight=label,
            )
    elif status == "OK":
        logger.warning("Model not loaded — returning CV/feature results without classification.")

    return AnalysisResult(
        analysis_id=new_analysis_id(), timestamp=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        quality=quality, halo=halo_schema, spreading=spreading_schema, classification=classification,
        explainability=explainability, visualizations=visualizations,
        decision_support=build_decision_support(status, label, uncertain), status=status,
        input_type=input_type, processing_ms=int((time.perf_counter() - started) * 1000),
        patient_code=patient_code, comparison=comparison, video=video, model_card=model_card(),
    )


def persist(result: AnalysisResult, patient_id: int | None, performed_by: int | None) -> None:
    c = result.classification
    storage_service.save_analysis(
        analysis_id=result.analysis_id, timestamp=result.timestamp, quality_status=result.quality.status,
        research_classification=c.research_classification if c else None,
        confidence=c.confidence if c else None, uncertain=c.uncertain if c else None,
        result=result.model_dump(), patient_id=patient_id, performed_by=performed_by,
        input_type=result.input_type, frames_analyzed=result.video.frames_used if result.video else 1,
    )


def run_full_analysis(
    image_bytes: bytes, manual_roi: ROI | None = None, *, patient_id: int | None = None,
    patient_code: str | None = None, performed_by: int | None = None,
) -> AnalysisResult:
    started = time.perf_counter()
    image = load_image_from_bytes(image_bytes)
    check = validate_sample(image)
    if not check.ok:
        raise NotASampleError(check.reason, check.metrics)  # nothing analysed, nothing stored
    frame = analyze_frame(image, manual_roi=manual_roi)
    result = assemble_result(frame, input_type="image", started=started, patient_code=patient_code)
    persist(result, patient_id, performed_by)
    return result
