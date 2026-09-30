"""Research-mode operations: generate the synthetic dataset, train models, evaluate them.

Shared by scripts/{generate_dataset,train,evaluate}.py (CLI) and api/routes_research.py
(HTTP) so there is exactly one implementation of each step.

Training uses only the `train` split; `validation` is reserved for future hyperparameter
tuning (not done in this pass — see docs/validation.md); `test` is the untouched holdout
used by evaluate_models(). Splits are session-grouped by synthetic_generator.py already.

Only the four decision-support classes (csf_like/saline_like/saliva_like/other) are fed to
the classifier. `invalid` (no-halo) synthetic samples are used to check that halo detection
correctly rejects them (mixture ratio below the literature-reported threshold) — they never
reach the classifier, mirroring the live pipeline where a NO_HALO_DETECTED sample never gets
classified either.
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
import logging
from pathlib import Path

import cv2
import joblib
import numpy as np

from app.config import settings
from app.feature_engineering.feature_vector import FEATURE_COLUMNS, build_feature_vector, feature_dict_to_row
from app.image_processing.halo_detection import detect_halo
from app.image_processing.roi_detection import detect_sample_region
from app.models.calibration import calibrate_and_fit
from app.models.classical_ml import MODEL_BUILDERS
from app.models.ensemble import ensemble_predict
from app.models.uncertainty import fit_class_gaussians
from app.spreading_analysis.spreading import compute_spreading_profile

logger = logging.getLogger(__name__)

CLASSIFIER_CLASSES = list(settings.class_labels)  # csf_like, saline_like, saliva_like, other


def generate_synthetic_dataset(sessions_per_class: int = 40, seed: int = 42) -> dict:
    from datasets.synthetic_generator import generate_dataset

    metadata_path = generate_dataset(settings.dataset_dir, sessions_per_class=sessions_per_class, seed=seed)
    with metadata_path.open() as f:
        n_rows = sum(1 for _ in csv.DictReader(f))
    return {"metadata_path": str(metadata_path), "n_samples": n_rows}


def _read_metadata() -> list[dict]:
    metadata_path = settings.dataset_dir / "metadata.csv"
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"No dataset found at {metadata_path}. Run generate_synthetic_dataset() first."
        )
    with metadata_path.open() as f:
        return list(csv.DictReader(f))


def _extract_features_for_split(rows: list[dict], split: str, classes: list[str]) -> tuple[np.ndarray, np.ndarray, int]:
    """Returns (X, y_idx, n_dropped_no_halo) for classifier-relevant classes only."""
    X_list: list[list[float]] = []
    y_list: list[int] = []
    dropped = 0

    for row in rows:
        if row["split"] != split or row["label"] not in classes:
            continue
        image_path = settings.dataset_dir / row["split"] / row["label"] / f"{row['sample_id']}.png"
        image_bgr = cv2.imread(str(image_path))
        if image_bgr is None:
            logger.warning("Could not read %s", image_path)
            continue

        roi = detect_sample_region(image_bgr)
        halo = detect_halo(image_bgr, roi)
        if not halo.detected:
            dropped += 1
            continue

        spreading = compute_spreading_profile(halo, roi)
        features = build_feature_vector(image_bgr, roi, halo, spreading)
        X_list.append(feature_dict_to_row(features))
        y_list.append(classes.index(row["label"]))

    return np.array(X_list, dtype=np.float64), np.array(y_list, dtype=np.int64), dropped


def invalid_class_rejection_rate(rows: list[dict], split: str = "test") -> dict:
    """Sanity check: 'invalid' (no-halo) synthetic samples should be flagged
    NO_HALO_DETECTED, never fed to the classifier. Reports how often that holds."""
    total = 0
    correctly_rejected = 0
    for row in rows:
        if row["split"] != split or row["label"] != "invalid":
            continue
        total += 1
        image_path = settings.dataset_dir / row["split"] / row["label"] / f"{row['sample_id']}.png"
        image_bgr = cv2.imread(str(image_path))
        if image_bgr is None:
            continue
        roi = detect_sample_region(image_bgr)
        halo = detect_halo(image_bgr, roi)
        if not halo.detected:
            correctly_rejected += 1
    rate = correctly_rejected / total if total else None
    return {"invalid_samples_tested": total, "correctly_rejected": correctly_rejected,
            "rejection_rate": round(rate, 4) if rate is not None else None}


def train_models() -> dict:
    rows = _read_metadata()
    X_train, y_train, dropped = _extract_features_for_split(rows, "train", CLASSIFIER_CLASSES)
    if X_train.shape[0] == 0:
        raise RuntimeError("No training samples extracted — check dataset generation.")

    models = {}
    for name, builder in MODEL_BUILDERS.items():
        models[name] = calibrate_and_fit(builder, X_train, y_train, method="isotonic", cv=5)
        joblib.dump(models[name], settings.models_dir / f"{name}.joblib")

    gaussians = fit_class_gaussians(X_train, y_train, n_classes=len(CLASSIFIER_CLASSES))
    joblib.dump(gaussians, settings.models_dir / "gaussians.joblib")

    metadata = {
        "model_version": settings.model_version,
        "classes": CLASSIFIER_CLASSES,
        "feature_columns": FEATURE_COLUMNS,
        "trained_on": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "n_train_samples": int(X_train.shape[0]),
        "n_dropped_no_halo": dropped,
        "synthetic": True,
        "disclaimer": "SYNTHETIC/DEMO DATA — not derived from real biological samples, not clinically validated.",
        "metrics": {},
    }
    (settings.models_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return metadata


def evaluate_models() -> dict:
    from app.evaluation.evaluate import full_evaluation_report

    rows = _read_metadata()
    X_test, y_test, dropped = _extract_features_for_split(rows, "test", CLASSIFIER_CLASSES)
    if X_test.shape[0] == 0:
        raise RuntimeError("No test samples extracted — check dataset generation / train_models() first.")

    models = {name: joblib.load(settings.models_dir / f"{name}.joblib") for name in MODEL_BUILDERS}

    per_sample_proba = []
    for i in range(X_test.shape[0]):
        x_row = X_test[i]
        per_model_proba = {name: m.predict_proba(x_row.reshape(1, -1))[0] for name, m in models.items()}
        ensemble = ensemble_predict(per_model_proba, CLASSIFIER_CLASSES)
        per_sample_proba.append([ensemble.class_probabilities[c] for c in CLASSIFIER_CLASSES])

    proba = np.array(per_sample_proba)
    y_pred = proba.argmax(axis=1)

    report = full_evaluation_report(y_test, y_pred, proba, CLASSIFIER_CLASSES)
    report["n_test_samples"] = int(X_test.shape[0])
    report["n_dropped_no_halo"] = dropped
    report["halo_gate_check_on_invalid_class"] = invalid_class_rejection_rate(rows, "test")

    metadata_path = settings.models_dir / "metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text())
        metadata["metrics"] = report
        metadata_path.write_text(json.dumps(metadata, indent=2))

    return report
