from app.image_processing.roi_detection import ROI, detect_sample_region


def test_detects_roi_near_true_center(ring_image_factory):
    image = ring_image_factory(size=400, center=(200, 200), inner_r=60, outer_r=120)
    roi = detect_sample_region(image)
    assert abs(roi.center_x - 200) < 25
    assert abs(roi.center_y - 200) < 25
    assert roi.radius > 60


def test_manual_roi_override_is_respected(ring_image):
    manual = ROI(center_x=10, center_y=10, radius=5, method="manual", confidence=1.0)
    roi = detect_sample_region(ring_image, manual_roi=manual)
    assert roi is manual


def test_offcenter_ring_detected(ring_image_factory):
    image = ring_image_factory(size=400, center=(150, 250), inner_r=50, outer_r=100)
    roi = detect_sample_region(image)
    assert abs(roi.center_x - 150) < 30
    assert abs(roi.center_y - 250) < 30
