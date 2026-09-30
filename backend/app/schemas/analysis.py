"""API response models. `research_classification` is used deliberately instead of a field
named `diagnosis` — see docs/architecture.md and the project's medical-safety constraint.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class QualitySchema(BaseModel):
    status: str
    score: float
    reasons: list[str] = Field(default_factory=list)


class HaloSchema(BaseModel):
    detected: bool
    center_x: float
    center_y: float
    inner_radius: float
    outer_radius: float
    halo_width: float
    circularity: float
    symmetry_score: float
    confidence: float
    messages: list[str] = Field(default_factory=list)


class SpreadingSchema(BaseModel):
    spread_radius_normalized: float
    spread_area_normalized: float
    central_stain_area_normalized: float
    outer_diffusion_area_normalized: float
    diffusion_index: float
    directional_variance: float


class ClassificationSchema(BaseModel):
    research_classification: str
    confidence: float
    class_probabilities: dict[str, float]
    uncertain: bool
    disagreement: float
    model_version: str
    synthetic_training_data: bool = True


class FeatureContribution(BaseModel):
    feature: str
    shap_value: float


class ExplainabilitySchema(BaseModel):
    top_features: list[FeatureContribution] = Field(default_factory=list)


class VisualizationsSchema(BaseModel):
    overlay_png_base64: str | None = None
    radial_profile_png_base64: str | None = None
    probability_chart_png_base64: str | None = None
    feature_importance_png_base64: str | None = None


class DecisionSupportSchema(BaseModel):
    message: str
    recommend_lab_confirmation: bool
    disclaimer: str = (
        "AI image analysis is a decision-support screening tool and is NOT a medical "
        "diagnosis or confirmation of CSF. The halo/double-ring pattern is not specific "
        "to CSF — saline and other clear fluids can produce the same pattern. Beta-2 "
        "transferrin laboratory testing is the recognized specific confirmatory method."
    )


class AnalysisResult(BaseModel):
    analysis_id: str
    timestamp: str
    quality: QualitySchema
    halo: HaloSchema | None = None
    spreading: SpreadingSchema | None = None
    classification: ClassificationSchema | None = None
    explainability: ExplainabilitySchema | None = None
    visualizations: VisualizationsSchema | None = None
    decision_support: DecisionSupportSchema
    status: str  # "OK" | "RECAPTURE_NEEDED" | "NO_HALO_DETECTED"


class HistoryItem(BaseModel):
    analysis_id: str
    timestamp: str
    quality_status: str
    research_classification: str | None
    confidence: float | None
    uncertain: bool | None


class HealthResponse(BaseModel):
    status: str
    model_version: str
    model_loaded: bool


class ModelInfoResponse(BaseModel):
    model_version: str
    classes: list[str]
    trained_on: str
    metrics: dict
    disclaimer: str = "Trained and evaluated on SYNTHETIC/DEMO data only. Not clinically validated."
