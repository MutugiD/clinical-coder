import httpx
import pytest

from clinical_scribe.config import Settings
from clinical_scribe.errors import StageError
from clinical_scribe.readiness import check


def test_unreachable_gemini(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("private request information")

    monkeypatch.setattr(httpx, "get", fail)
    with pytest.raises(StageError, match="Gemini unavailable") as error:
        check(Settings(gemini_api_key="test-key"))
    assert "private" not in str(error.value)


def test_readiness_timeout_does_not_echo_secret(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ReadTimeout("test-key")

    monkeypatch.setattr(httpx, "get", fail)
    with pytest.raises(StageError) as error:
        check(Settings(gemini_api_key="test-key"))
    assert "test-key" not in str(error.value)
