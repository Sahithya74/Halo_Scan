"""The sample gate: halo test images must pass; faces and unrelated photos must be refused
(HTTP 422, nothing stored)."""
import glob
import io
from pathlib import Path

import cv2
import numpy as np
import pytest
from skimage import data

from app.image_processing.sample_validation import validate_sample
from app.services import storage_service

SAMPLES = sorted(glob.glob(str(Path(__file__).resolve().parent.parent / "datasets/synthetic/samples/*.png")))


def _bgr(rgb_or_gray) -> np.ndarray:
    im = rgb_or_gray
    if im.ndim == 2:
        return cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    return cv2.cvtColor(im, cv2.COLOR_RGB2BGR)


@pytest.mark.parametrize("path", SAMPLES, ids=[Path(p).stem for p in SAMPLES])
def test_reference_halo_samples_pass(path):
    check = validate_sample(cv2.imread(path))
    assert check.ok, (check.reason, check.metrics)


def test_halo_sample_still_passes_as_large_jpeg_photo():
    img = cv2.resize(cv2.imread(SAMPLES[0]), (3024, 3024))
    img = cv2.imdecode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])[1], cv2.IMREAD_COLOR)
    assert validate_sample(img).ok


def test_face_is_rejected_as_face():
    check = validate_sample(_bgr(data.astronaut()))
    assert not check.ok
    assert check.reason == "face"


@pytest.mark.parametrize("name", ["chelsea", "coffee", "rocket", "camera", "brick", "colorwheel", "retina", "clock"])
def test_unrelated_photos_rejected(name):
    check = validate_sample(_bgr(getattr(data, name)()))
    assert not check.ok, (name, check.metrics)


def test_face_upload_returns_422_and_is_not_stored(client_for, make_patient):
    nurse = client_for("nurse")
    pid = make_patient()["patient"]["id"]
    face_jpg = cv2.imencode(".jpg", _bgr(data.astronaut()))[1].tobytes()
    resp = nurse.post("/api/analyze", data={"patient_id": pid},
                      files={"file": ("me.jpg", io.BytesIO(face_jpg), "image/jpeg")})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "not_a_sample" and detail["reason"] == "face"
    assert storage_service.list_history(patient_id=pid) == []


def test_video_of_unrelated_scene_rejected(client_for, make_patient, tmp_path):
    frame = cv2.resize(_bgr(data.coffee()), (480, 320))
    path = str(tmp_path / "v.mp4")
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 5, (480, 320))
    for i in range(20):
        w.write(np.roll(frame, i, axis=1))
    w.release()
    nurse = client_for("nurse")
    pid = make_patient()["patient"]["id"]
    resp = nurse.post("/api/analyze", data={"patient_id": pid},
                      files={"file": ("v.mp4", io.BytesIO(open(path, "rb").read()), "video/mp4")})
    assert resp.status_code == 422
    assert storage_service.list_history(patient_id=pid) == []


def test_large_photo_response_is_bounded(client_for, make_patient):
    """Regression: a 12-megapixel phone photo used to produce a ~14 MB response."""
    nurse = client_for("nurse")
    pid = make_patient()["patient"]["id"]
    big = cv2.resize(cv2.imread(SAMPLES[0]), (3500, 3500))
    resp = nurse.post("/api/analyze", data={"patient_id": pid},
                      files={"file": ("big.jpg", io.BytesIO(cv2.imencode(".jpg", big)[1].tobytes()), "image/jpeg")})
    assert resp.status_code == 200, resp.text
    assert len(resp.content) < 3_000_000
