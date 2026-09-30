"""Loads trained model artifacts once and exposes a single `predict` entry point that
combines the ensemble, calibration, uncertainty, and SHAP explanation — the ML half of
services/analysis_service.py's pipeline.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import joblib
import numpy as np

from app.config import settings
from app.explainability.shap_explainer import (
    build_tree_explainer,
    extract_underlying_random_forest,
    top_contributing_features,
)
from app.models.ensemble import EnsembleResult, ensemble_predict
from app.models.uncertainty import ClassGaussian, UncertaintyAssessment, assess_uncertainty

logger = logging.getLogger(__name__)

MODEL_FILES = {
    "logistic_regression": "logistic_regression.joblib",
    "random_forest": "random_forest.joblib",
    "svm": "svm.joblib",
}


@dataclass
class PredictionOutcome:
    ensemble: EnsembleResult
    uncertainty: UncertaintyAssessment
    top_features: list[dict[str, float]]


class ModelRegistry:
    def __init__(self) -> None:
        self.models: dict[str, object] = {}
        self.gaussians: list[ClassGaussian] | None = None
        self.classes: list[str] = list(settings.class_labels)
        self.metadata: dict = {}
        self.shap_explainer = None
        self.loaded = False

    def load(self) -> bool:
        try:
            for name, filename in MODEL_FILES.items():
                path = settings.models_dir / filename
                self.models[name] = joblib.load(path)
            self.gaussians = joblib.load(settings.models_dir / "gaussians.joblib")
            metadata_path = settings.models_dir / "metadata.json"
            if metadata_path.exists():
                self.metadata = json.loads(metadata_path.read_text())
                self.classes = self.metadata.get("classes", self.classes)

            rf_calibrated = self.models.get("random_forest")
            rf = extract_underlying_random_forest(rf_calibrated)
            self.shap_explainer = build_tree_explainer(rf)

            self.loaded = True
        except FileNotFoundError:
            logger.warning("Trained model artifacts not found under %s — run scripts/train.py first.",
                            settings.models_dir)
            self.loaded = False
        return self.loaded

    def predict(self, x_row: np.ndarray) -> PredictionOutcome:
        if not self.loaded:
            raise RuntimeError("Models not loaded. Run scripts/train.py, then restart the service.")

        per_model_proba = {
            name: model.predict_proba(x_row.reshape(1, -1))[0] for name, model in self.models.items()
        }
        ensemble = ensemble_predict(per_model_proba, self.classes)

        uncertainty = assess_uncertainty(
            x_row, self.gaussians, ensemble.confidence, ensemble.disagreement,
        )

        predicted_idx = self.classes.index(ensemble.predicted_label)
        top_features = top_contributing_features(self.shap_explainer, x_row, predicted_idx)

        return PredictionOutcome(ensemble=ensemble, uncertainty=uncertainty, top_features=top_features)


registry = ModelRegistry()
