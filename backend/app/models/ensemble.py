"""Weighted probability ensemble across the calibrated classical models + model
disagreement detection (spec section 12). No CNN branch yet (see docs/dataset.md /
build plan) — this ensembles Logistic Regression, Random Forest, and SVM.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class EnsembleResult:
    class_probabilities: dict[str, float]
    predicted_label: str
    confidence: float
    disagreement: float
    per_model_probabilities: dict[str, dict[str, float]] = field(default_factory=dict)


def ensemble_predict(
    per_model_proba: dict[str, np.ndarray],
    classes: list[str],
    weights: dict[str, float] | None = None,
) -> EnsembleResult:
    names = list(per_model_proba.keys())
    stack = np.stack([per_model_proba[n] for n in names], axis=0)  # (n_models, n_classes)

    if weights is None:
        weight_arr = np.ones(len(names))
    else:
        weight_arr = np.array([weights.get(n, 1.0) for n in names])
    weight_arr = weight_arr / weight_arr.sum()

    ensemble_proba = (stack * weight_arr[:, None]).sum(axis=0)
    predicted_idx = int(np.argmax(ensemble_proba))

    # Disagreement: mean per-class std across models, normalized 0..1-ish. High std on the
    # winning class in particular is the strongest signal of genuine model conflict.
    per_class_std = stack.std(axis=0)
    disagreement = float(np.clip(per_class_std.mean() * len(names), 0.0, 1.0))

    return EnsembleResult(
        class_probabilities={c: round(float(p), 4) for c, p in zip(classes, ensemble_proba)},
        predicted_label=classes[predicted_idx],
        confidence=round(float(ensemble_proba[predicted_idx]), 4),
        disagreement=round(disagreement, 4),
        per_model_probabilities={
            n: {c: round(float(p), 4) for c, p in zip(classes, per_model_proba[n])} for n in names
        },
    )
