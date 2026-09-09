"""Check configured extraction dependencies without generating clinical content."""

import httpx

from clinical_scribe.config import Settings
from clinical_scribe.contracts import schema_registry
from clinical_scribe.errors import StageError


def check() -> None:
    settings = Settings.from_env()
    schema_registry()
    try:
        response = httpx.get(settings.endpoint("/api/tags"), timeout=10)
        response.raise_for_status()
        models = response.json()["models"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise StageError("check", "Ollama unavailable or invalid model listing", "Ollama") from exc
    if not isinstance(models, list) or any(not isinstance(m, dict) for m in models):
        raise StageError("check", "invalid model listing", "Ollama")
    if not any(m.get("name") == settings.model for m in models):
        raise StageError("check", f"configured model is not installed: {settings.model}")
