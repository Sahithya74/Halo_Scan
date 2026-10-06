import io
from pathlib import Path

from app.services import storage_service


_SAMPLE = Path(__file__).resolve().parent.parent / "datasets/synthetic/samples/csf_like_example.png"


def _png() -> bytes:
    # A real reference sample: hand-drawn hard-edged grey circles are (correctly) refused by
    # the sample gate as a solid object rather than a soaked-in fluid stain.
    return _SAMPLE.read_bytes()


def test_admin_can_create_staff_and_gets_temp_password(client_for):
    admin = client_for("admin")
    resp = admin.post("/api/admin/users", json={"username": "new.nurse1", "role": "nurse", "display_name": "N One"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["must_change_password"] is True
    assert len(body["temporary_password"]) >= 10


def test_admin_cannot_create_patient_accounts_directly(client_for):
    resp = client_for("admin").post("/api/admin/users", json={"username": "p_x1", "role": "patient", "display_name": "P"})
    assert resp.status_code == 400


def test_nurse_cannot_reach_admin(client_for):
    nurse = client_for("nurse")
    assert nurse.get("/api/admin/users").status_code == 403
    assert nurse.get("/api/admin/audit").status_code == 403


def test_patient_cannot_run_analysis_or_list_patients(client_for, make_patient):
    patient = make_patient()["patient"]
    p = client_for("patient", patient_id=patient["id"])
    resp = p.post("/api/analyze", data={"patient_id": patient["id"]},
                  files={"file": ("s.png", io.BytesIO(_png()), "image/png")})
    assert resp.status_code == 403
    assert p.get("/api/patients").status_code == 403


def test_staff_registers_patient_with_login(client_for):
    doctor = client_for("doctor")
    resp = doctor.post("/api/patients", json={"mrn": "RBAC-100", "name": "Ravi Kumar", "dob": "1985-04-02", "sex": "M"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["patient"]["name"] == "Ravi Kumar"
    assert body["login"]["username"].startswith("pt-")
    dup = doctor.post("/api/patients", json={"mrn": "rbac-100", "name": "Someone Else"})
    assert dup.status_code == 400  # MRN match is case-insensitive via the blind index


def test_patient_sees_only_own_analyses(client_for, make_patient):
    nurse = client_for("nurse")
    mine = make_patient()["patient"]
    other = make_patient()["patient"]
    for pid in (mine["id"], other["id"]):
        r = nurse.post("/api/analyze", data={"patient_id": pid},
                       files={"file": ("s.png", io.BytesIO(_png()), "image/png")})
        assert r.status_code == 200, r.text

    other_analysis = storage_service.list_history(patient_id=other["id"])[0]["analysis_id"]
    mine_analysis = storage_service.list_history(patient_id=mine["id"])[0]["analysis_id"]

    p = client_for("patient", patient_id=mine["id"])
    assert p.get(f"/api/analysis/{mine_analysis}").status_code == 200
    assert p.get(f"/api/analysis/{other_analysis}").status_code == 404
    history = p.get("/api/history", params={"patient_id": other["id"]}).json()
    assert history and all(h["patient_id"] == mine["id"] for h in history)
    assert all(h["patient_id"] == mine["id"] for h in p.get("/api/me/analyses").json())


def test_admin_cannot_read_patient_results(client_for, make_patient):
    nurse = client_for("nurse")
    pid = make_patient()["patient"]["id"]
    aid = nurse.post("/api/analyze", data={"patient_id": pid},
                     files={"file": ("s.png", io.BytesIO(_png()), "image/png")}).json()["analysis_id"]
    assert client_for("admin").get(f"/api/analysis/{aid}").status_code == 403


def test_last_admin_cannot_be_deactivated(client_for):
    admin = client_for("admin")
    # Deactivating yourself is always refused.
    assert admin.patch(f"/api/admin/users/{admin.user['id']}", json={"active": False}).status_code == 400
