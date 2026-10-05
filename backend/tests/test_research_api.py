import pytest

from app.config import settings

_STUB = {"metadata_path": "stub", "n_samples": 0}


@pytest.fixture(autouse=True)
def stub_dataset_generation(monkeypatch):
    monkeypatch.setattr("app.services.research_service.generate_synthetic_dataset",
                        lambda sessions_per_class=40: _STUB)
    original = settings.research_api_key
    yield
    settings.research_api_key = original


def test_research_requires_login(anon_client):
    assert anon_client.post("/api/research/upload-dataset").status_code == 401


def test_research_rejects_non_admin(client_for):
    assert client_for("doctor").post("/api/research/upload-dataset").status_code == 403


def test_research_allows_admin_session(client_for):
    resp = client_for("admin").post("/api/research/upload-dataset")
    assert resp.status_code == 200
    assert resp.json() == _STUB


def test_research_api_key_works_when_configured(anon_client):
    settings.research_api_key = "secret123"
    resp = anon_client.post("/api/research/upload-dataset", headers={"X-API-Key": "secret123"})
    assert resp.status_code == 200


def test_research_wrong_api_key_rejected(anon_client):
    settings.research_api_key = "secret123"
    resp = anon_client.post("/api/research/upload-dataset", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_research_api_key_ignored_when_not_configured(anon_client):
    settings.research_api_key = ""
    resp = anon_client.post("/api/research/upload-dataset", headers={"X-API-Key": "anything"})
    assert resp.status_code == 401
