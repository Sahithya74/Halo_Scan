import numpy as np

from app.evaluation.evaluate import classification_metrics, csf_like_binary_metrics, full_evaluation_report, roc_pr_auc
from app.models.calibration import calibration_report, expected_calibration_error, multiclass_brier_score


def test_expected_calibration_error_is_zero_for_perfect_calibration():
    # 100% confident and 100% correct -> confidence exactly matches empirical accuracy
    # in the one occupied bin -> ECE should be ~0.
    proba = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    y_true = np.array([0, 0, 1])
    ece = expected_calibration_error(proba, y_true, n_bins=10)
    assert ece < 1e-6


def test_expected_calibration_error_penalizes_overconfidence():
    # Model is 95% confident but wrong half the time -> high ECE.
    proba = np.array([[0.95, 0.05]] * 10)
    y_true = np.array([0, 1] * 5)
    ece = expected_calibration_error(proba, y_true, n_bins=10)
    assert ece > 0.3


def test_multiclass_brier_score_zero_for_perfect_predictions():
    proba = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    y_true = np.array([0, 1, 2])
    score = multiclass_brier_score(proba, y_true, n_classes=3)
    assert score == 0.0


def test_calibration_report_has_expected_keys():
    proba = np.array([[0.6, 0.4], [0.3, 0.7]])
    y_true = np.array([0, 1])
    report = calibration_report(proba, y_true, n_classes=2)
    assert set(report.keys()) == {"expected_calibration_error", "brier_score"}


def test_classification_metrics_perfect_predictions():
    y_true = np.array([0, 1, 2, 0, 1, 2])
    y_pred = y_true.copy()
    classes = ["a", "b", "c"]
    metrics = classification_metrics(y_true, y_pred, classes)
    assert metrics["accuracy"] == 1.0
    assert metrics["f1_macro"] == 1.0
    assert metrics["confusion_matrix"] == [[2, 0, 0], [0, 2, 0], [0, 0, 2]]


def test_classification_metrics_with_errors():
    y_true = np.array([0, 0, 1, 1])
    y_pred = np.array([0, 1, 1, 1])
    classes = ["a", "b"]
    metrics = classification_metrics(y_true, y_pred, classes)
    assert metrics["accuracy"] == 0.75


def test_roc_pr_auc_handles_single_class_gracefully():
    # Only one true class present for "b" -> roc_auc_score would error; must return None.
    y_true = np.array([0, 0, 0])
    proba = np.array([[0.9, 0.1], [0.8, 0.2], [0.7, 0.3]])
    result = roc_pr_auc(y_true, proba, ["a", "b"])
    assert result["roc_auc_per_class"]["b"] is None
    assert result["pr_auc_per_class"]["b"] is None


def test_csf_like_binary_metrics_perfect():
    classes = ["csf_like", "other"]
    y_true = np.array([0, 0, 1, 1])
    y_pred = np.array([0, 0, 1, 1])
    metrics = csf_like_binary_metrics(y_true, y_pred, classes)
    assert metrics["csf_like_sensitivity"] == 1.0
    assert metrics["csf_like_specificity"] == 1.0
    assert metrics["csf_like_ppv"] == 1.0
    assert metrics["csf_like_npv"] == 1.0


def test_csf_like_binary_metrics_absent_class_returns_empty():
    classes = ["saline_like", "other"]
    y_true = np.array([0, 1])
    y_pred = np.array([0, 1])
    assert csf_like_binary_metrics(y_true, y_pred, classes) == {}


def test_full_evaluation_report_includes_disclaimer_and_calibration():
    classes = ["csf_like", "saline_like"]
    y_true = np.array([0, 0, 1, 1])
    y_pred = np.array([0, 1, 1, 1])
    proba = np.array([[0.7, 0.3], [0.4, 0.6], [0.2, 0.8], [0.3, 0.7]])
    report = full_evaluation_report(y_true, y_pred, proba, classes)
    assert "disclaimer" in report
    assert "SYNTHETIC" in report["disclaimer"]
    assert "calibration" in report
    assert "csf_like_sensitivity" in report
