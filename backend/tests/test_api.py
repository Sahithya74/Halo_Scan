import io

import cv2
import numpy as np


def _ring_png_bytes() -> bytes:
    image = np.full((500, 500, 3), (246, 243, 238), dtype=np.uint8)
    cv2.circle(image, (250, 250), 130, (200, 200, 180), -1)
    cv2.circle(image, (250, 250), 60, (28, 32, 118), -1)
    image = cv2.GaussianBlur(image, (5, 5), 0)
    ok, buf = cv2.imencode(".png", image)
    assert ok
    return buf.tobytes()


def test_health_endpoint_is_public(anon_client):
    resp = anon_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_analyze_requires_login(anon_client, make_patient):
    patient = make_patient()["patient"]
    resp = anon_client.post("/api/analyze", data={"patient_id": patient["id"]},
                            files={"file": ("s.png", io.BytesIO(_ring_png_bytes()), "image/png")})
    assert resp.status_code == 401


def test_analyze_returns_decision_support_disclaimer(client_for, make_patient):
    nurse = client_for("nurse")
    patient = make_patient()["patient"]
    resp = nurse.post("/api/analyze", data={"patient_id": patient["id"]},
                      files={"file": ("s.png", io.BytesIO(_ring_png_bytes()), "image/png")})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "NOT a medical diagnosis" in body["decision_support"]["disclaimer"]
    assert body["status"] in ("OK", "NO_HALO_DETECTED", "RECAPTURE_NEEDED")
    assert body["input_type"] == "image"
    assert body["patient_code"] == patient["patient_code"]
    assert body["processing_ms"] is not None
    assert body["visualizations"]["source_image_jpeg_base64"]
    # Structural safety constraint: never a field literally called "diagnosis".
    assert "diagnosis" not in body


def test_analyze_unknown_patient_404(client_for):
    doctor = client_for("doctor")
    resp = doctor.post("/api/analyze", data={"patient_id": 999999},
                       files={"file": ("s.png", io.BytesIO(_ring_png_bytes()), "image/png")})
    assert resp.status_code == 404


def test_analyze_rejects_unsupported_content_type(client_for, make_patient):
    nurse = client_for("nurse")
    patient = make_patient()["patient"]
    resp = nurse.post("/api/analyze", data={"patient_id": patient["id"]},
                      files={"file": ("s.txt", io.BytesIO(b"not an image"), "text/plain")})
    assert resp.status_code == 415


def test_quality_check_endpoint(client_for):
    doctor = client_for("doctor")
    resp = doctor.post("/api/quality-check", files={"file": ("s.png", io.BytesIO(_ring_png_bytes()), "image/png")})
    assert resp.status_code == 200
    assert resp.json()["status"] in ("GOOD", "ACCEPTABLE", "POOR")


def test_history_endpoint_returns_list(client_for):
    resp = client_for("doctor").get("/api/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_security_headers_present(anon_client):
    resp = anon_client.get("/api/health")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
    assert resp.headers["Cache-Control"] == "no-store"
