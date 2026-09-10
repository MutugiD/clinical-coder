import pytest
from fastapi.testclient import TestClient

from clinical_scribe.contracts import empty_note
from clinical_scribe.errors import ProviderError
from clinical_scribe.services import create_app


@pytest.mark.parametrize("stage", ["extract", "validate", "resolve", "knowledge"])
def test_health_and_input_schema(stage, monkeypatch):
    monkeypatch.setenv("SCRIBE_OFFLINE", "true")
    with TestClient(create_app(stage)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["service"] == stage and health.json()["version"]
        response = client.post("/process", json={})
        assert response.status_code == 422
        assert response.json()["error"]["stage"] == stage


@pytest.mark.parametrize("body", ['{"note":{},"note":{}}', '{"note":NaN}', "not JSON"])
def test_http_strict_json(body):
    with TestClient(create_app("resolve")) as client:
        assert client.post("/process", content=body).status_code == 422


def test_output_schema_cannot_be_bypassed(monkeypatch):
    monkeypatch.setattr("clinical_scribe.boundaries.resolve", lambda *a: {"broken": True})
    with TestClient(create_app("resolve")) as client:
        response = client.post(
            "/process",
            json={
                "note": empty_note(),
                "register": "kind,code,name,synonyms\ndrug,X,Example,alias\n",
            },
        )
        assert response.status_code == 500
        assert response.json()["error"]["source"] == "response"


def test_provider_unavailable_returns_503(monkeypatch):
    monkeypatch.setenv("SCRIBE_OFFLINE", "false")

    def fail(*args):
        raise ProviderError("extract", "dependency unavailable")

    monkeypatch.setattr("clinical_scribe.providers.generate", fail)
    with TestClient(create_app("extract")) as client:
        response = client.post("/process", json={"transcript": "[00:00] NURSE: Pulse 80."})
        assert response.status_code == 503


def test_non_extraction_service_ignores_provider_environment(monkeypatch):
    monkeypatch.setenv("SCRIBE_PROVIDER", "invalid")
    with TestClient(create_app("resolve")) as client:
        response = client.post(
            "/process",
            json={
                "note": empty_note(),
                "register": "kind,code,name,synonyms\ndrug,X,Example,alias\n",
            },
        )
        assert response.status_code == 200


def test_unexpected_failure_does_not_echo_internal_data(monkeypatch):
    def fail(*args):
        raise RuntimeError("private input")

    monkeypatch.setattr("clinical_scribe.boundaries.validate", fail)
    with TestClient(create_app("validate")) as client:
        response = client.post("/process", json={"transcript": "example", "note": empty_note()})
        assert response.status_code == 500
        assert "private input" not in response.text
