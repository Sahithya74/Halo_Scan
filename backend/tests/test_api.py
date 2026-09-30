import io

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _ring_png_bytes() -> bytes:
    image = np.full((500, 500, 3), (246, 243, 238), dtype=np.uint8)
    cv2.circle(image, (250, 250), 130, (200, 200, 180), -1)
    cv2.circle(image, (250, 250), 60, (28, 32, 118), -1)
    image = cv2.GaussianBlur(image, (5, 5), 0)
    ok, buf = cv2.imencode(".png", image)
    assert ok
    return buf.tobytes()


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_analyze_returns_decision_support_disclaimer(client):
    png_bytes = _ring_png_bytes()
    resp = client.post("/api/analyze", files={"file": ("sample.png", io.BytesIO(png_bytes), "image/png")})
    assert resp.status_code == 200
    body = resp.json()
    assert "decision_support" in body
    assert "NOT a medical diagnosis" in body["decision_support"]["disclaimer"]
    assert body["status"] in ("OK", "NO_HALO_DETECTED", "RECAPTURE_NEEDED")
    # Structural safety constraint: never a field literally called "diagnosis".
    assert "diagnosis" not in body


def test_analyze_rejects_unsupported_content_type(client):
    resp = client.post("/api/analyze", files={"file": ("sample.txt", io.BytesIO(b"not an image"), "text/plain")})
    assert resp.status_code == 415


def test_quality_check_endpoint(client):
    png_bytes = _ring_png_bytes()
    resp = client.post("/api/quality-check", files={"file": ("sample.png", io.BytesIO(png_bytes), "image/png")})
    assert resp.status_code == 200
    assert resp.json()["status"] in ("GOOD", "ACCEPTABLE", "POOR")


def test_history_endpoint_returns_list(client):
    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
