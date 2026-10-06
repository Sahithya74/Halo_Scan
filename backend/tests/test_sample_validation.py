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


_WALL = (232, 234, 236)


def _on_wall(img: np.ndarray, scale: float) -> np.ndarray:
    canvas = np.full((960, 1280, 3), _WALL, np.uint8)
    f = cv2.resize(img, None, fx=scale, fy=scale)[:960, :1280]
    y, x = (960 - f.shape[0]) // 2, (1280 - f.shape[1]) // 2
    canvas[y:y + f.shape[0], x:x + f.shape[1]] = f
    return canvas


def _selfie_variants() -> dict:
    face = _bgr(data.astronaut())[20:230, 150:330]
    tilt = lambda d: cv2.warpAffine(_on_wall(face, 2.5), cv2.getRotationMatrix2D((640, 480), d, 1), (1280, 960),
                                    borderValue=_WALL)
    return {
        "close-up on wall": _on_wall(face, 3.9), "tilted 30": tilt(30), "tilted 45": tilt(45),
        "upper half of face": _on_wall(face[:125], 3.5), "lower half of face": _on_wall(face[85:], 3.5),
        "dim": (_on_wall(face, 2.5) * 0.4).astype(np.uint8),
    }


@pytest.mark.parametrize("variant", list(_selfie_variants()))
def test_webcam_style_selfies_rejected_as_face(variant):
    """Hand-held webcam selfies: tilted, partial, close-up or dim faces against a plain wall."""
    check = validate_sample(_selfie_variants()[variant])
    assert not check.ok and check.reason == "face", (variant, check.reason, check.metrics)


@pytest.mark.parametrize("variant", list(_selfie_variants()))
def test_selfies_rejected_even_if_face_detector_misses(variant, monkeypatch):
    """Second line of defence: the fluid-stain checks alone must refuse a selfie."""
    import app.image_processing.sample_validation as sv
    monkeypatch.setattr(sv, "_count_faces", lambda img: 0)
    assert not sv.validate_sample(_selfie_variants()[variant]).ok


def _disc(color, blur=0, size=150):
    c = np.full((960, 1280, 3), _WALL, np.uint8)
    cv2.circle(c, (640, 480), size, color, -1, cv2.LINE_AA)
    return cv2.GaussianBlur(c, (blur, blur), 0) if blur else c


@pytest.mark.parametrize("name,img", [
    ("black sticker", _disc((25, 25, 25))),
    ("red sticker", _disc((40, 40, 200))),
    ("red sticker, slightly blurry", _disc((40, 40, 200), blur=9)),
    ("brown coin", _disc((40, 70, 110))),
    ("backlit head silhouette", cv2.GaussianBlur(cv2.ellipse(np.full((960, 1280, 3), 245, np.uint8), (640, 520),
                                                             (230, 300), 0, 0, 360, (30, 30, 35), -1), (15, 15), 0)),
])
def test_stain_lookalikes_rejected(name, img):
    """Round dark objects on a white surface look like a stain to simple checks; their sharp
    outline / neutral colour shows they aren't soaked-in fluid."""
    check = validate_sample(img)
    assert not check.ok and check.reason == "not_fluid_stain", (name, check.reason, check.metrics)


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
