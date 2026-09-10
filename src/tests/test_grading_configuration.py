import subprocess
import sys

import httpx
import pytest

from clinical_scribe.cli import parser
from clinical_scribe.config import Settings
from clinical_scribe.errors import StageError
from clinical_scribe.readiness import check


def response(status=200, body=None):
    return httpx.Response(status, json=body, request=httpx.Request("GET", "https://example.test"))


def test_default_gemini_model(monkeypatch):
    for variable in ("SCRIBE_PROVIDER", "GEMINI_MODEL"):
        monkeypatch.delenv(variable, raising=False)
    settings = Settings.from_env()
    assert settings.provider == "gemini"
    assert settings.gemini_model == "gemini-3.1-flash-lite"


def test_explicit_provider_wins_and_ignores_other_provider_config(monkeypatch):
    monkeypatch.setenv("SCRIBE_PROVIDER", "unsupported")
    monkeypatch.setenv("GEMINI_API_KEY", "example-test-key")
    settings = Settings.from_env("gemini")
    assert settings.provider == "gemini"
    assert settings.gemini_model == "gemini-3.1-flash-lite"
    assert "example-test-key" not in repr(settings)


def test_offline_ignores_invalid_provider_environment(monkeypatch):
    monkeypatch.setenv("SCRIBE_PROVIDER", "unsupported")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "invalid")
    assert Settings.from_env(offline=True).offline


def test_unknown_provider_rejected(monkeypatch):
    monkeypatch.setenv("SCRIBE_PROVIDER", "unsupported")
    with pytest.raises(StageError, match="configuration"):
        Settings.from_env()


@pytest.mark.parametrize(
    "command,args",
    [
        ("check", []),
        ("extract", ["--transcript", "t.txt", "--out", "n.json"]),
        (
            "pipeline",
            [
                "--transcript",
                "t.txt",
                "--register",
                "r.csv",
                "--source",
                "g.txt",
                "--out",
                "outputs",
            ],
        ),
    ],
)
def test_mutually_exclusive_execution_modes(command, args):
    result = subprocess.run(
        [sys.executable, "scribe", command, *args, "--provider", "gemini", "--offline"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "not allowed" in result.stderr
    assert "--offline" in result.stderr


@pytest.mark.parametrize("mode", [["--offline"], ["--provider", "gemini"]])
def test_arguments_on_extract_and_pipeline(mode):
    extract = parser().parse_args(["extract", "--transcript", "x", "--out", "y", *mode])
    pipeline = parser().parse_args(
        [
            "pipeline",
            "--transcript",
            "x",
            "--register",
            "r",
            "--source",
            "s",
            "--out",
            "y",
            *mode,
        ]
    )
    assert extract.offline == pipeline.offline
    assert extract.provider == pipeline.provider


def test_removed_provider_is_rejected():
    with pytest.raises(SystemExit):
        parser().parse_args(["check", "--provider", "ollama"])
    with pytest.raises(StageError, match="configuration"):
        Settings.from_env("ollama")


def test_missing_gemini_key_does_not_contact_network(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("missing key must not trigger a request")

    monkeypatch.setattr(httpx, "get", fail)
    with pytest.raises(StageError, match="GEMINI_API_KEY is missing"):
        check(Settings(provider="gemini"))


def test_gemini_key_uses_header(monkeypatch):
    settings = Settings(provider="gemini", gemini_api_key="example-test-key")

    def metadata(url, **kwargs):
        assert "example-test-key" not in url
        assert kwargs["headers"] == {"x-goog-api-key": "example-test-key"}
        assert url.endswith("/models/gemini-3.1-flash-lite")
        return response(
            body={
                "name": "models/gemini-3.1-flash-lite",
                "supportedGenerationMethods": ["generateContent"],
            }
        )

    monkeypatch.setattr(httpx, "get", metadata)
    assert check(settings) is None


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_gemini_failure_never_falls_back_or_echoes_key(monkeypatch, status):
    calls = []

    def reject(url, **kwargs):
        calls.append(url)
        return response(status, {"error": "example-test-key"})

    monkeypatch.setattr(httpx, "get", reject)
    with pytest.raises(StageError, match=f"HTTP {status}") as error:
        check(Settings(provider="gemini", gemini_api_key="example-test-key"))
    assert "example-test-key" not in str(error.value)
    assert calls == [
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite"
    ]


@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {"name": "different-model"},
        {
            "name": "models/gemini-3.1-flash-lite",
            "supportedGenerationMethods": None,
        },
    ],
)
def test_malformed_gemini_metadata(monkeypatch, body):
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: response(body=body))
    with pytest.raises(StageError, match="Gemini"):
        check(Settings(provider="gemini", gemini_api_key="example-test-key"))


def test_offline_readiness_requires_artifacts(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("offline mode must not contact providers")

    monkeypatch.setattr(httpx, "get", fail)
    monkeypatch.setattr(
        "clinical_scribe.readiness.Path.is_file",
        lambda path: str(path).replace("\\", "/") == "prompts/extract.txt",
    )
    with pytest.raises(StageError, match="offline replay artifacts missing"):
        check(Settings(offline=True))
