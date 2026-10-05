import datetime as _dt

from app.config import settings
from app.db import connect, iso, utcnow
from tests.conftest import TEST_PASSWORD, login


def test_login_success_sets_httponly_session_cookie(anon_client, make_user):
    _, username, password = make_user("doctor")
    resp = anon_client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    assert resp.json()["role"] == "doctor"
    set_cookie = ",".join(resp.headers.get_list("set-cookie"))
    assert "halo_session=" in set_cookie and "HttpOnly" in set_cookie and "SameSite=strict" in set_cookie


def test_wrong_password_is_generic_401(anon_client, make_user):
    _, username, _ = make_user("nurse")
    resp = anon_client.post("/api/auth/login", json={"username": username, "password": "nope-nope-1"})
    assert resp.status_code == 401
    unknown = anon_client.post("/api/auth/login", json={"username": "ghost_user", "password": "nope-nope-1"})
    assert unknown.status_code == 401
    assert resp.json()["detail"] == unknown.json()["detail"]  # no username enumeration


def test_lockout_after_max_failures(anon_client, make_user):
    _, username, password = make_user("nurse")
    for _ in range(settings.max_failed_logins):
        anon_client.post("/api/auth/login", json={"username": username, "password": "bad-password-9"})
    # Even the correct password is refused while locked.
    resp = anon_client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 429


def test_password_stored_as_argon2_not_plaintext(make_user):
    uid, _, password = make_user("doctor")
    with connect() as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (uid,)).fetchone()[0]
    assert stored.startswith("$argon2id$")
    assert password not in stored


def test_wrong_portal_rejected(anon_client, make_user):
    _, username, password = make_user("patient")
    resp = anon_client.post("/api/auth/login", json={"username": username, "password": password, "portal": "staff"})
    assert resp.status_code == 403


def test_logout_revokes_session(client_for):
    c = client_for("doctor")
    assert c.get("/api/auth/me").status_code == 200
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401


def test_state_changing_request_requires_csrf(client_for, make_patient):
    c = client_for("nurse")
    del c.headers["X-CSRF-Token"]
    resp = c.post("/api/patients", json={"mrn": "CSRF-1", "name": "X"})
    assert resp.status_code == 403
    assert "CSRF" in resp.json()["detail"]


def test_idle_session_expires(client_for):
    c = client_for("doctor")
    stale = iso(utcnow() - _dt.timedelta(minutes=settings.session_idle_minutes + 1))
    with connect() as conn:
        conn.execute("UPDATE sessions SET last_seen = ?", (stale,))
    assert c.get("/api/auth/me").status_code == 401


def test_forced_password_change_blocks_other_endpoints(anon_client, make_user):
    _, username, password = make_user("doctor", must_change=True)
    login(anon_client, username, password)
    assert anon_client.get("/api/auth/me").json()["must_change_password"] is True
    assert anon_client.get("/api/history").status_code == 403

    weak = anon_client.post("/api/auth/change-password",
                            json={"current_password": password, "new_password": "short"})
    assert weak.status_code == 400
    ok = anon_client.post("/api/auth/change-password",
                          json={"current_password": password, "new_password": "BrandNew2026pass"})
    assert ok.status_code == 200
    assert anon_client.get("/api/history").status_code == 200
    assert TEST_PASSWORD != "BrandNew2026pass"
