"""Shared pytest fixtures.

- Hand-drawn synthetic test images for fast, deterministic CV unit tests.
- An isolated database and encryption key for the whole test session, so tests never touch
  the real analysis_history.db or secrets/data.key.
- Signed-in TestClients for each role.
"""
from __future__ import annotations

import itertools
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="halo_test_"))
settings.history_db_path = _TMP / "test.db"
settings.secrets_dir = _TMP / "secrets"
settings.secrets_dir.mkdir(parents=True, exist_ok=True)
settings.data_key = ""
settings.research_api_key = ""

TEST_PASSWORD = "CorrectHorse42battery"
_counter = itertools.count(1)


def _unique(prefix: str) -> str:
    return f"{prefix}{next(_counter)}"


@pytest.fixture
def make_user():
    """Creates a user directly (bypassing the API) and returns (id, username, password)."""
    from app.services import accounts_service

    def factory(role: str, patient_id: int | None = None, must_change: bool = False):
        username = _unique(f"t_{role}_")
        uid = accounts_service.create_user(username, TEST_PASSWORD, role, f"Test {role}", None,
                                           patient_id=patient_id, must_change_password=must_change)
        return uid, username, TEST_PASSWORD
    return factory


@pytest.fixture
def make_patient():
    from app.services import accounts_service

    def factory(create_login: bool = False):
        return accounts_service.register_patient(_unique("MRN-"), "Jane Test", "1990-01-01", "F",
                                                 created_by=None, create_login=create_login)
    return factory


def login(client, username: str, password: str, portal: str | None = None):
    resp = client.post("/api/auth/login", json={"username": username, "password": password, "portal": portal})
    assert resp.status_code == 200, resp.text
    client.headers["X-CSRF-Token"] = client.cookies["halo_csrf"]
    return client


@pytest.fixture
def client_for(make_user):
    """client_for("nurse") -> signed-in TestClient (user dict in client.user)."""
    from fastapi.testclient import TestClient

    from app.main import app
    clients = []

    def factory(role: str, patient_id: int | None = None):
        uid, username, password = make_user(role, patient_id=patient_id)
        c = TestClient(app)
        c.__enter__()
        clients.append(c)
        login(c, username, password)
        c.user = {"id": uid, "username": username, "role": role, "patient_id": patient_id}
        return c

    yield factory
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def anon_client():
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_login_attempts():
    """Keep the per-IP failed-login limit from leaking between tests (all share one IP)."""
    yield
    from app.db import connect
    with connect() as conn:
        conn.execute("DELETE FROM login_attempts")


def _make_ring_image(size: int = 400, center=None, inner_r: int = 60, outer_r: int = 120,
                      background=(250, 248, 245), ring_color=(150, 150, 130),
                      center_color=(28, 32, 118)) -> np.ndarray:
    # Background vs ring vs center are deliberately high-contrast (~100+ gray levels apart
    # at each boundary) so this represents a genuinely *visible* ring — the low-contrast
    # case (ring barely distinguishable from background) is a real failure mode worth its
    # own test, not what "detects_clear_ring" is meant to exercise.
    if center is None:
        center = (size // 2, size // 2)
    image = np.full((size, size, 3), background, dtype=np.uint8)
    cv2.circle(image, center, outer_r, ring_color, -1)
    cv2.circle(image, center, inner_r, center_color, -1)
    image = cv2.GaussianBlur(image, (5, 5), 0)
    return image


@pytest.fixture
def ring_image() -> np.ndarray:
    return _make_ring_image()


@pytest.fixture
def ring_image_factory():
    return _make_ring_image


@pytest.fixture
def blurry_dark_image() -> np.ndarray:
    image = np.full((400, 400, 3), (20, 20, 20), dtype=np.uint8)
    noise = np.random.default_rng(0).normal(0, 2, image.shape)
    image = np.clip(image.astype(np.float64) + noise, 0, 255).astype(np.uint8)
    return cv2.GaussianBlur(image, (25, 25), 0)


@pytest.fixture
def good_quality_flat_image() -> np.ndarray:
    rng = np.random.default_rng(1)
    base = np.full((500, 500, 3), 150, dtype=np.uint8)
    noise = rng.normal(0, 25, base.shape)
    image = np.clip(base.astype(np.float64) + noise, 0, 255).astype(np.uint8)
    cv2.circle(image, (250, 250), 100, (60, 60, 60), -1)
    return image
