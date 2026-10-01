import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import require_research_api_key
from app.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def reset_api_key():
    original = settings.research_api_key
    yield
    settings.research_api_key = original


def test_require_research_api_key_passes_when_unconfigured():
    settings.research_api_key = ""
    require_research_api_key(provided_key=None)  # must not raise


def test_require_research_api_key_rejects_missing_key_when_configured():
    settings.research_api_key = "secret123"
    with pytest.raises(HTTPException) as exc_info:
        require_research_api_key(provided_key=None)
    assert exc_info.value.status_code == 401


def test_require_research_api_key_rejects_wrong_key():
    settings.research_api_key = "secret123"
    with pytest.raises(HTTPException) as exc_info:
        require_research_api_key(provided_key="wrong")
    assert exc_info.value.status_code == 401


def test_require_research_api_key_accepts_correct_key():
    settings.research_api_key = "secret123"
    require_research_api_key(provided_key="secret123")  # must not raise


def test_research_endpoint_open_by_default(monkeypatch):
    settings.research_api_key = ""
    monkeypatch.setattr(
        "app.services.research_service.generate_synthetic_dataset",
        lambda sessions_per_class=40: {"metadata_path": "stub", "n_samples": 0},
    )
    with TestClient(app) as client:
        resp = client.post("/api/research/upload-dataset")
    assert resp.status_code == 200


def test_research_endpoint_rejects_without_key_when_configured(monkeypatch):
    settings.research_api_key = "secret123"
    monkeypatch.setattr(
        "app.services.research_service.generate_synthetic_dataset",
        lambda sessions_per_class=40: {"metadata_path": "stub", "n_samples": 0},
    )
    with TestClient(app) as client:
        resp = client.post("/api/research/upload-dataset")
    assert resp.status_code == 401


def test_research_endpoint_accepts_correct_key(monkeypatch):
    settings.research_api_key = "secret123"
    monkeypatch.setattr(
        "app.services.research_service.generate_synthetic_dataset",
        lambda sessions_per_class=40: {"metadata_path": "stub", "n_samples": 0},
    )
    with TestClient(app) as client:
        resp = client.post("/api/research/upload-dataset", headers={"X-API-Key": "secret123"})
    assert resp.status_code == 200
