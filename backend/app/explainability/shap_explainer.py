"""SHAP explainability for the Random Forest branch (spec section 14).

We explain the Random Forest specifically (via TreeExplainer, exact and fast) rather than
the full calibrated ensemble — CalibratedClassifierCV wraps the base estimator, so we
reach into `calibrated_classifiers_[i].estimator` to get the underlying RandomForestClassifier
for explanation purposes, while the ensemble's own probabilities (not SHAP's) still drive
the reported classification.
"""
from __future__ import annotations

import numpy as np
import shap
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline

from app.feature_engineering.feature_vector import FEATURE_COLUMNS


def extract_underlying_random_forest(calibrated: CalibratedClassifierCV) -> RandomForestClassifier:
    estimator = calibrated.calibrated_classifiers_[0].estimator
    if isinstance(estimator, Pipeline):
        estimator = estimator.named_steps["clf"]
    return estimator


def build_tree_explainer(rf: RandomForestClassifier) -> shap.TreeExplainer:
    return shap.TreeExplainer(rf)


def _select_class_values(shap_values, predicted_class_idx: int, n_features: int) -> np.ndarray:
    """SHAP's multiclass return shape has changed across versions: a list of n_classes
    arrays in older releases, or a single ndarray in newer ones — and when it's an
    ndarray, which axis is "classes" vs "features" has also varied. Rather than assume
    one layout, squeeze out the size-1 sample axis and pick the feature axis by matching
    its length to n_features (features/classes/samples are different sizes here, so this
    is unambiguous), which works regardless of which SHAP version is installed.
    """
    if isinstance(shap_values, list):
        return np.asarray(shap_values[predicted_class_idx])[0]

    arr = np.squeeze(np.asarray(shap_values))
    if arr.ndim == 1:
        return arr
    if arr.shape[0] == n_features:
        return arr[:, predicted_class_idx]
    return arr[predicted_class_idx, :]


def top_contributing_features(
    explainer: shap.TreeExplainer, x_row: np.ndarray, predicted_class_idx: int, top_n: int = 5,
) -> list[dict[str, float]]:
    shap_values = explainer.shap_values(x_row.reshape(1, -1))
    class_values = _select_class_values(shap_values, predicted_class_idx, n_features=x_row.shape[0])

    order = np.argsort(np.abs(class_values))[::-1][:top_n]
    return [
        {"feature": FEATURE_COLUMNS[i], "shap_value": round(float(class_values[i]), 4)}
        for i in order
    ]
