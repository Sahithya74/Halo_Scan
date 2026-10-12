"""Model evaluation (spec section 17). Every number produced here must be reported to the
user with the "synthetic data, not clinical validation" caveat — see docs/validation.md.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from app.models.calibration import calibration_report


def classification_metrics(y_true_idx: np.ndarray, y_pred_idx: np.ndarray, classes: list[str]) -> dict:
    accuracy = float(np.mean(y_true_idx == y_pred_idx))
    precision_macro = float(precision_score(y_true_idx, y_pred_idx, average="macro", zero_division=0))
    recall_macro = float(recall_score(y_true_idx, y_pred_idx, average="macro", zero_division=0))
    f1_macro = float(f1_score(y_true_idx, y_pred_idx, average="macro", zero_division=0))
    cm = confusion_matrix(y_true_idx, y_pred_idx, labels=list(range(len(classes)))).tolist()

    return {
        "accuracy": round(accuracy, 4),
        "precision_macro": round(precision_macro, 4),
        "recall_macro": round(recall_macro, 4),
        "f1_macro": round(f1_macro, 4),
        "confusion_matrix": cm,
        "confusion_matrix_labels": classes,
    }


def roc_pr_auc(y_true_idx: np.ndarray, proba: np.ndarray, classes: list[str]) -> dict:
    n_classes = len(classes)
    one_hot = np.eye(n_classes)[y_true_idx]
    roc_auc = {}
    pr_auc = {}
    for i, cls in enumerate(classes):
        if len(np.unique(one_hot[:, i])) < 2:
            roc_auc[cls] = None
            pr_auc[cls] = None
            continue
        roc_auc[cls] = round(float(roc_auc_score(one_hot[:, i], proba[:, i])), 4)
        pr_auc[cls] = round(float(average_precision_score(one_hot[:, i], proba[:, i])), 4)
    return {"roc_auc_per_class": roc_auc, "pr_auc_per_class": pr_auc}


def csf_like_binary_metrics(y_true_idx: np.ndarray, y_pred_idx: np.ndarray, classes: list[str]) -> dict:
    """Sensitivity/specificity/PPV/NPV treating csf_like as the positive class, since this
    is the class the medical-safety framing cares about most (spec section 17)."""
    if "csf_like" not in classes:
        return {}
    positive_idx = classes.index("csf_like")
    y_true_bin = (y_true_idx == positive_idx)
    y_pred_bin = (y_pred_idx == positive_idx)

    tp = int(np.sum(y_true_bin & y_pred_bin))
    tn = int(np.sum(~y_true_bin & ~y_pred_bin))
    fp = int(np.sum(~y_true_bin & y_pred_bin))
    fn = int(np.sum(y_true_bin & ~y_pred_bin))

    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    ppv = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0

    return {
        "csf_like_sensitivity": round(sensitivity, 4),
        "csf_like_specificity": round(specificity, 4),
        "csf_like_ppv": round(ppv, 4),
        "csf_like_npv": round(npv, 4),
        "csf_like_confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "note": "Computed on SYNTHETIC data. NOT a clinical sensitivity/specificity estimate.",
    }


def family_metrics(y_true_idx: np.ndarray, proba: np.ndarray, classes: list[str]) -> dict:
    """Metrics at the fluid-family level (clear fluid / mucus-rich / other), using family
    probabilities = sums of the calibrated class probabilities."""
    from app.models.families import FAMILY_MIN_CONFIDENCE, family_index_map

    names, fam_of = family_index_map(classes)
    fam_proba = np.zeros((proba.shape[0], len(names)))
    for ci, fi in enumerate(fam_of):
        fam_proba[:, fi] += proba[:, ci]
    y_true = np.array([fam_of[i] for i in y_true_idx])
    y_pred = fam_proba.argmax(axis=1)
    base = classification_metrics(y_true, y_pred, names)

    clear = names.index("clear_fluid")
    t, p = y_true == clear, y_pred == clear
    tp, tn, fp, fn = int(np.sum(t & p)), int(np.sum(~t & ~p)), int(np.sum(~t & p)), int(np.sum(t & ~p))
    confident = fam_proba.max(axis=1) >= FAMILY_MIN_CONFIDENCE
    return {
        **base,
        "per_family_sensitivity": {
            n: round(float(np.mean(y_pred[y_true == i] == i)), 4) for i, n in enumerate(names) if np.any(y_true == i)
        },
        "clear_fluid_sensitivity": round(tp / (tp + fn), 4) if tp + fn else None,
        "clear_fluid_specificity": round(tn / (tn + fp), 4) if tn + fp else None,
        "confident_fraction": round(float(confident.mean()), 4),
        "accuracy_when_confident": round(float(np.mean(y_pred[confident] == y_true[confident])), 4) if confident.any() else None,
        "calibration": calibration_report(fam_proba, y_true, len(names)),
    }


def full_evaluation_report(
    y_true_idx: np.ndarray, y_pred_idx: np.ndarray, proba: np.ndarray, classes: list[str],
) -> dict:
    report = {}
    report.update(classification_metrics(y_true_idx, y_pred_idx, classes))
    report.update(roc_pr_auc(y_true_idx, proba, classes))
    report.update(csf_like_binary_metrics(y_true_idx, y_pred_idx, classes))
    report["calibration"] = calibration_report(proba, y_true_idx, len(classes))
    report["family"] = family_metrics(y_true_idx, proba, classes)
    report["disclaimer"] = "All metrics computed on SYNTHETIC/DEMO data. Not a clinical validation study."
    return report
