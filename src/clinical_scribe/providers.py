"""Extraction-only provider adapters with bounded requests and no implicit fallback."""

import json

import httpx

from clinical_scribe.config import Settings
from clinical_scribe.errors import ProviderError, StageError


def generate(settings: Settings, prompt: str, payload: dict, schema: dict) -> tuple[str, dict]:
    if settings.offline:
        raise ProviderError("extract", "provider invocation is forbidden in offline mode")
    try:
        key = settings.gemini_api_key.get_secret_value()
        if not key:
            raise ProviderError("extract", "GEMINI_API_KEY is missing")
        response = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + settings.gemini_model
            + ":generateContent",
            headers={"x-goog-api-key": key},
            json={
                "systemInstruction": {"parts": [{"text": prompt}]},
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": json.dumps(payload, ensure_ascii=False)}],
                    }
                ],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 4096,
                    "responseMimeType": "application/json",
                    "responseJsonSchema": schema,
                },
            },
            timeout=settings.timeout,
        )
        response.raise_for_status()
        data = response.json()
        candidate = data["candidates"][0]
        if candidate.get("finishReason") != "STOP":
            raise ProviderError("extract", "Gemini response was blocked or incomplete")
        content = "".join(p.get("text", "") for p in candidate["content"]["parts"])
        metadata = {"model": "gemini/" + data.get("modelVersion", settings.gemini_model)}
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("extract", "provider returned empty content")
        return content, metadata
    except httpx.HTTPStatusError as exc:
        raise ProviderError(
            "extract", f"{settings.provider} HTTP {exc.response.status_code}"
        ) from exc
    except httpx.TimeoutException as exc:
        raise ProviderError(
            "extract", f"{settings.provider} timed out after {settings.timeout:g}s"
        ) from exc
    except httpx.HTTPError as exc:
        raise ProviderError("extract", f"{settings.provider} connection failed") from exc
    except (AttributeError, KeyError, IndexError, TypeError, ValueError) as exc:
        if isinstance(exc, StageError):
            raise
        raise ProviderError("extract", f"{settings.provider} returned an invalid response") from exc
