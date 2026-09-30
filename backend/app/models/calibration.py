"""Probability calibration (spec section 13).

Raw softmax/SVM probabilities overstate confidence. We wrap each base model in
CalibratedClassifierCV (isotonic regression, 5-fold internal CV) so the reported
"AI confidence" is closer to a true probability of correctness — never presented as
"medical certainty" (that framing lives in services/analysis_service.py's decision
message, not here).
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
from sklearn.pipeline import Pipeline


def calibrate_and_fit(
    builder: Callable[[], Pipeline], X: np.ndarray, y: np.ndarray,
    method: str = "isotonic", cv: int = 5,
) -> CalibratedClassifierCV:
    base = builder()
    calibrated = CalibratedClassifierCV(base, method=method, cv=cv)
    calibrated.fit(X, y)
    return calibrated


def expected_calibration_error(proba: np.ndarray, y_true_idx: np.ndarray, n_bins: int = 10) -> float:
    confidences = proba.max(axis=1)
    predictions = proba.argmax(axis=1)
    accuracies = (predictions == y_true_idx).astype(float)

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(confidences)
    if n == 0:
        return 0.0
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (confidences > lo) & (confidences <= hi) if i > 0 else (confidences >= lo) & (confidences <= hi)
        if not np.any(mask):
            continue
        bin_acc = accuracies[mask].mean()
        bin_conf = confidences[mask].mean()
        ece += (mask.sum() / n) * abs(bin_acc - bin_conf)
    return float(ece)


def multiclass_brier_score(proba: np.ndarray, y_true_idx: np.ndarray, n_classes: int) -> float:
    one_hot = np.eye(n_classes)[y_true_idx]
    scores = [
        brier_score_loss(one_hot[:, c], proba[:, c]) for c in range(n_classes)
    ]
    return float(np.mean(scores))


def calibration_report(proba: np.ndarray, y_true_idx: np.ndarray, n_classes: int) -> dict:
    return {
        "expected_calibration_error": round(expected_calibration_error(proba, y_true_idx), 4),
        "brier_score": round(multiclass_brier_score(proba, y_true_idx, n_classes), 4),
    }
