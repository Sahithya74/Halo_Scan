import numpy as np

from app.models.ensemble import ensemble_predict
from app.models.uncertainty import assess_uncertainty, fit_class_gaussians


def test_ensemble_predict_picks_majority_class():
    classes = ["csf_like", "saline_like", "saliva_like", "other"]
    per_model = {
        "m1": np.array([0.7, 0.1, 0.1, 0.1]),
        "m2": np.array([0.6, 0.2, 0.1, 0.1]),
        "m3": np.array([0.65, 0.15, 0.1, 0.1]),
    }
    result = ensemble_predict(per_model, classes)
    assert result.predicted_label == "csf_like"
    assert result.confidence > 0.5
    assert result.disagreement < 0.2  # models agree closely


def test_ensemble_predict_flags_disagreement():
    classes = ["csf_like", "saline_like", "saliva_like", "other"]
    per_model = {
        "m1": np.array([0.9, 0.03, 0.03, 0.04]),
        "m2": np.array([0.05, 0.85, 0.05, 0.05]),
        "m3": np.array([0.1, 0.1, 0.7, 0.1]),
    }
    result = ensemble_predict(per_model, classes)
    assert result.disagreement > 0.2


def test_fit_class_gaussians_and_distance():
    rng = np.random.default_rng(0)
    X = np.vstack([
        rng.normal(0, 1, size=(20, 5)),
        rng.normal(10, 1, size=(20, 5)),
    ])
    y = np.array([0] * 20 + [1] * 20)
    gaussians = fit_class_gaussians(X, y, n_classes=2)
    assert len(gaussians) == 2

    near_point = np.zeros(5)
    far_point = np.full(5, 100.0)

    result_near = assess_uncertainty(near_point, gaussians, ensemble_confidence=0.9, ensemble_disagreement=0.05)
    result_far = assess_uncertainty(far_point, gaussians, ensemble_confidence=0.9, ensemble_disagreement=0.05)

    assert result_far.ood_distance > result_near.ood_distance
    assert result_far.is_out_of_distribution is True
