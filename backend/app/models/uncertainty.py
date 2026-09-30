"""Out-of-distribution / uncertainty detection (spec section 26 — Uncertainty).

Combines three independent uncertain-signals rather than trusting raw softmax alone:
  1. Mahalanobis distance to the nearest per-class training-feature distribution
     (catches samples that don't resemble ANY training class — true novelty/OOD)
  2. Ensemble confidence below threshold
  3. Ensemble model disagreement above threshold
Any one of these routes the result to "uncertain" with a lab-confirmation recommendation,
rather than forcing a confident label the models don't actually support.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.config import settings


@dataclass
class ClassGaussian:
    mean: np.ndarray
    inv_cov: np.ndarray


@dataclass
class UncertaintyAssessment:
    is_uncertain: bool
    is_out_of_distribution: bool
    ood_distance: float
    low_confidence: bool
    high_disagreement: bool
    reasons: list[str] = field(default_factory=list)


def fit_class_gaussians(X: np.ndarray, y_idx: np.ndarray, n_classes: int, reg: float = 1e-2) -> list[ClassGaussian]:
    gaussians = []
    n_features = X.shape[1]
    for c in range(n_classes):
        Xc = X[y_idx == c]
        if Xc.shape[0] < 2:
            gaussians.append(ClassGaussian(mean=np.zeros(n_features), inv_cov=np.eye(n_features)))
            continue
        mean = Xc.mean(axis=0)
        cov = np.cov(Xc, rowvar=False) + reg * np.eye(n_features)
        inv_cov = np.linalg.pinv(cov)
        gaussians.append(ClassGaussian(mean=mean, inv_cov=inv_cov))
    return gaussians


def _mahalanobis(x: np.ndarray, g: ClassGaussian) -> float:
    diff = x - g.mean
    return float(np.sqrt(max(diff @ g.inv_cov @ diff.T, 0.0)))


def min_class_distance(x: np.ndarray, gaussians: list[ClassGaussian]) -> float:
    return min(_mahalanobis(x, g) for g in gaussians)


def assess_uncertainty(
    x: np.ndarray, gaussians: list[ClassGaussian], ensemble_confidence: float, ensemble_disagreement: float,
) -> UncertaintyAssessment:
    ood_distance = min_class_distance(x, gaussians)
    is_ood = ood_distance > settings.ood_mahalanobis_threshold
    low_confidence = ensemble_confidence < settings.min_confidence_for_confident_label
    high_disagreement = ensemble_disagreement > settings.disagreement_uncertain_threshold

    reasons = []
    if is_ood:
        reasons.append("Sample's features are unlike anything seen during training (out-of-distribution).")
    if low_confidence:
        reasons.append("Model confidence is below the threshold for a confident classification.")
    if high_disagreement:
        reasons.append("The ensemble models disagree significantly on this sample.")

    return UncertaintyAssessment(
        is_uncertain=is_ood or low_confidence or high_disagreement,
        is_out_of_distribution=is_ood,
        ood_distance=round(ood_distance, 3),
        low_confidence=low_confidence,
        high_disagreement=high_disagreement,
        reasons=reasons,
    )
