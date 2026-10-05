import io
import os
import tempfile

import cv2
import numpy as np
import pytest

from datasets.synthetic_generator import render_sample


def _make_video(seconds: float, fps: int = 6, size: int = 512, label: str = "saliva_like",
                fourcc: str = "mp4v", suffix: str = ".mp4") -> bytes:
    rng = np.random.default_rng(3)
    base, _ = render_sample(rng, label)
    base = cv2.resize(base, (size, size))
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*fourcc), fps, (size, size))
        assert writer.isOpened(), f"{fourcc} writer unavailable"
        for i in range(int(seconds * fps)):
            jitter = np.roll(base, shift=(i % 3) - 1, axis=1)  # tiny hand-shake movement
            writer.write(jitter)
        writer.release()
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.remove(path)


@pytest.fixture(scope="module")
def short_video() -> bytes:
    return _make_video(3)


def test_video_analysis_aggregates_frames(client_for, make_patient, short_video):
    nurse = client_for("nurse")
    pid = make_patient()["patient"]["id"]
    resp = nurse.post("/api/analyze", data={"patient_id": pid},
                      files={"file": ("clip.mp4", io.BytesIO(short_video), "video/mp4")})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["input_type"] == "video"
    v = body["video"]
    assert 2.5 <= v["duration_s"] <= 3.5
    assert v["frames_sampled"] >= 4
    assert len(v["frames"]) == v["frames_sampled"]
    assert all(f["thumbnail_jpeg_base64"] for f in v["frames"])
    assert body["processing_ms"] < 60_000
    if v["frames_used"]:
        probs = body["classification"]["class_probabilities"]
        assert abs(sum(probs.values()) - 1.0) < 0.02
        assert body["visualizations"]["frame_timeline_png_base64"]
        assert 0.0 <= v["frame_agreement"] <= 1.0


def test_video_codec_param_in_content_type_accepted(client_for, make_patient, short_video):
    nurse = client_for("nurse")
    pid = make_patient()["patient"]["id"]
    resp = nurse.post("/api/analyze", data={"patient_id": pid},
                      files={"file": ("clip.mp4", io.BytesIO(short_video), "video/mp4;codecs=avc1")})
    assert resp.status_code == 200, resp.text


def test_browser_style_webm_accepted(client_for, make_patient):
    """Chrome/Edge/Firefox MediaRecorder output: WebM VP8 with a codecs parameter."""
    webm = _make_video(10, fps=10, size=480, fourcc="VP80", suffix=".webm")
    nurse = client_for("nurse")
    pid = make_patient()["patient"]["id"]
    resp = nurse.post("/api/analyze", data={"patient_id": pid},
                      files={"file": ("rec.webm", io.BytesIO(webm), "video/webm;codecs=vp8")})
    assert resp.status_code == 200, resp.text
    v = resp.json()["video"]
    assert 9.0 <= v["duration_s"] <= 11.0
    assert v["frames_sampled"] == 8


def test_too_long_video_rejected(client_for, make_patient):
    nurse = client_for("nurse")
    pid = make_patient()["patient"]["id"]
    long_video = _make_video(17, fps=2, size=320)
    resp = nurse.post("/api/analyze", data={"patient_id": pid},
                      files={"file": ("long.mp4", io.BytesIO(long_video), "video/mp4")})
    assert resp.status_code == 400
    assert "maximum" in resp.json()["detail"]


def test_garbage_video_rejected(client_for, make_patient):
    nurse = client_for("nurse")
    pid = make_patient()["patient"]["id"]
    resp = nurse.post("/api/analyze", data={"patient_id": pid},
                      files={"file": ("bad.mp4", io.BytesIO(b"\x00" * 2048), "video/mp4")})
    assert resp.status_code == 400
