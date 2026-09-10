"""Check selected dependencies and report unfinished execution paths explicitly."""

import shutil
from pathlib import Path

import httpx

from clinical_scribe.config import Settings
from clinical_scribe.contracts import schema_registry
from clinical_scribe.errors import StageError


def check_ollama(settings: Settings) -> None:
    if settings.base_url.host in {"localhost", "127.0.0.1", "::1", "[::1]"}:
        if shutil.which("ollama") is None:
            raise StageError(
                "check", "Ollama executable missing; install Ollama and add it to PATH"
            )
    try:
        response = httpx.get(settings.endpoint("/api/tags"), timeout=10)
        response.raise_for_status()
        models = response.json()["models"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise StageError(
            "check",
            "Ollama unavailable or invalid model listing; start `ollama serve` "
            "or check OLLAMA_BASE_URL",
            "Ollama",
        ) from exc
    if not isinstance(models, list) or any(not isinstance(m, dict) for m in models):
        raise StageError("check", "invalid model listing", "Ollama")
    if not any(m.get("name") == settings.model for m in models):
        raise StageError(
            "check", f"configured model is not installed; run `ollama pull {settings.model}`"
        )


def check_gemini(settings: Settings) -> None:
    key = settings.gemini_api_key.get_secret_value()
    if not key:
        raise StageError("check", "GEMINI_API_KEY is missing; export it for --provider gemini")
    try:
        response = httpx.get(
            "https://generativelanguage.googleapis.com/v1beta/models/" + settings.gemini_model,
            headers={"x-goog-api-key": key},
            timeout=10,
        )
        response.raise_for_status()
        model = response.json()
    except httpx.HTTPStatusError as exc:
        raise StageError(
            "check",
            f"Gemini readiness HTTP {exc.response.status_code}; check key and model",
            "Gemini",
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise StageError("check", "Gemini unavailable or invalid response", "Gemini") from exc
    if not isinstance(model, dict) or model.get("name") != "models/" + settings.gemini_model:
        raise StageError("check", "Gemini returned unexpected model metadata", "Gemini")
    methods = model.get("supportedGenerationMethods")
    if not isinstance(methods, list) or "generateContent" not in methods:
        raise StageError("check", "Gemini model does not advertise generateContent", "Gemini")


def check(settings: Settings | None = None) -> None:
    settings = settings or Settings.from_env()
    schema_registry()
    if settings.offline:
        if not Path("outputs/replay-manifest.json").is_file():
            raise StageError(
                "check",
                "offline replay artifacts missing: outputs/replay-manifest.json; "
                "offline extraction is not implemented in this milestone",
            )
        raise StageError("check", "offline extraction is not implemented in this milestone")
    if settings.provider == "gemini":
        check_gemini(settings)
    else:
        check_ollama(settings)
    raise StageError(
        "check", "provider dependencies found, but extraction is not implemented in this milestone"
    )
