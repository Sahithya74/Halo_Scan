from app.image_processing.quality import assess_quality


def test_good_quality_image_scores_high(good_quality_flat_image):
    result = assess_quality(good_quality_flat_image)
    assert result.status in ("GOOD", "ACCEPTABLE")
    assert result.score > 0.4


def test_blurry_dark_image_is_poor(blurry_dark_image):
    result = assess_quality(blurry_dark_image)
    assert result.status == "POOR"
    assert len(result.reasons) > 0


def test_low_resolution_image_flagged():
    import numpy as np
    tiny = np.full((50, 50, 3), 150, dtype="uint8")
    result = assess_quality(tiny)
    assert result.resolution_ok is False
    assert result.status == "POOR"


def test_quality_score_bounded(ring_image):
    result = assess_quality(ring_image)
    assert 0.0 <= result.score <= 1.0
