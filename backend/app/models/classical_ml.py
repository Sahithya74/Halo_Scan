"""Classical ML models trained on the extracted feature vector (spec section 10, Model 1).

Three complementary model families rather than one, per the spec: Logistic Regression
(linear baseline), Random Forest (non-linear, gives SHAP TreeExplainer support), and SVM
(RBF kernel, margin-based). XGBoost/LightGBM are intentionally skipped — see
backend/requirements.txt comment — sklearn's own models cover the same ground without
native-build friction on Windows.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


@dataclass
class TrainedModel:
    name: str
    pipeline: Pipeline
    classes: list[str]


def build_logistic_regression() -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])


def build_random_forest() -> Pipeline:
    return Pipeline([
        ("clf", RandomForestClassifier(
            n_estimators=300, max_depth=12, min_samples_leaf=3,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )),
    ])


def build_svm() -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", SVC(kernel="rbf", probability=True, class_weight="balanced", random_state=42)),
    ])


MODEL_BUILDERS = {
    "logistic_regression": build_logistic_regression,
    "random_forest": build_random_forest,
    "svm": build_svm,
}


def train_all(X: np.ndarray, y: np.ndarray, classes: list[str]) -> dict[str, TrainedModel]:
    trained: dict[str, TrainedModel] = {}
    for name, builder in MODEL_BUILDERS.items():
        pipeline = builder()
        pipeline.fit(X, y)
        trained[name] = TrainedModel(name=name, pipeline=pipeline, classes=classes)
    return trained
