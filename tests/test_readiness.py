import httpx
import pytest

from clinical_scribe.errors import StageError
from clinical_scribe.readiness import check


@pytest.fixture(autouse=True)
def local_dependencies(monkeypatch):
    monkeypatch.setenv("SCRIBE_PROVIDER", "ollama")
    monkeypatch.setattr("clinical_scribe.readiness.shutil.which", lambda name: "/bin/ollama")


def test_missing_model(monkeypatch):
    response = httpx.Response(200, json={"models": []}, request=httpx.Request("GET", "http://x"))
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: response)
    with pytest.raises(StageError, match="not installed"):
        check()


def test_unreachable_ollama(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(httpx, "get", fail)
    with pytest.raises(StageError, match="Ollama unavailable"):
        check()


@pytest.mark.parametrize("models", [None, "model", [None]])
def test_malformed_listing(monkeypatch, models):
    response = httpx.Response(
        200, json={"models": models}, request=httpx.Request("GET", "http://x")
    )
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: response)
    with pytest.raises(StageError, match="invalid model listing"):
        check()
