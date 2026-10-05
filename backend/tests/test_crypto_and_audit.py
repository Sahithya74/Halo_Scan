import pytest

from app.db import connect
from app.security import audit
from app.security.crypto import blind_index, decrypt_str, encrypt_str
from app.services import accounts_service, storage_service


def test_encrypt_roundtrip_and_ciphertext_differs():
    token = encrypt_str("Asha Menon")
    assert token != "Asha Menon"
    assert decrypt_str(token) == "Asha Menon"
    assert encrypt_str("Asha Menon") != token  # random IV each time


def test_blind_index_is_stable_and_case_insensitive():
    assert blind_index("mrn-77") == blind_index(" MRN-77 ")
    assert blind_index("MRN-77") != blind_index("MRN-78")


def test_patient_pii_not_stored_in_plaintext():
    result = accounts_service.register_patient("SECRET-MRN-55", "Priyanka Plaintext", "1999-09-09", "F",
                                               created_by=None, create_login=False)
    pid = result["patient"]["id"]
    with connect() as conn:
        row = dict(conn.execute("SELECT * FROM patients WHERE id = ?", (pid,)).fetchone())
    raw = " ".join(str(v) for v in row.values())
    assert "Priyanka" not in raw and "SECRET-MRN-55" not in raw and "1999-09-09" not in raw
    assert accounts_service.find_patient_by_mrn("secret-mrn-55")["name"] == "Priyanka Plaintext"


def test_stored_results_are_encrypted():
    storage_service.save_analysis("an_crypto_test", "2026-01-01T00:00:00+00:00", "GOOD", "csf_like", 0.7,
                                  False, {"marker": "VISIBLE-IF-PLAINTEXT"}, patient_id=None)
    with connect() as conn:
        raw = conn.execute("SELECT result_json FROM analyses WHERE analysis_id = 'an_crypto_test'").fetchone()[0]
    assert "VISIBLE-IF-PLAINTEXT" not in raw
    assert storage_service.get_analysis("an_crypto_test")["result"]["marker"] == "VISIBLE-IF-PLAINTEXT"


def test_audit_chain_verifies_and_detects_tampering():
    audit.record("unit_test_event", username="tester", detail="first")
    audit.record("unit_test_event", username="tester", detail="second")
    assert audit.verify_chain()["verified"] is True

    with connect() as conn:
        target = conn.execute("SELECT id FROM audit_log WHERE detail = 'first' ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute("UPDATE audit_log SET detail = 'edited' WHERE id = ?", (target,))
    result = audit.verify_chain()
    assert result["verified"] is False
    assert result["first_broken_id"] == target

    with connect() as conn:  # restore so later tests see a valid chain
        conn.execute("UPDATE audit_log SET detail = 'first' WHERE id = ?", (target,))
    assert audit.verify_chain()["verified"] is True


@pytest.mark.parametrize("action", ["login", "patient_register"])
def test_actions_are_audited(client_for, action):
    c = client_for("doctor")  # logs in
    if action == "patient_register":
        c.post("/api/patients", json={"mrn": "AUD-1-" + c.user["username"], "name": "Audit Me"})
    entries = audit.list_entries(limit=20)
    assert any(e["action"] == action and e["username"] == c.user["username"] for e in entries)
