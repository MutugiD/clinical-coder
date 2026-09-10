"""Explicit extraction configuration; no provider fallback."""

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from clinical_scribe.errors import StageError


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    provider: Literal["gemini"] = "gemini"
    offline: bool = False
    timeout: float = Field(default=180, gt=0, le=600)
    gemini_model: str = Field(default="gemini-3.1-flash-lite", pattern=r"^[a-z0-9.-]+$")
    gemini_api_key: SecretStr = SecretStr("")

    @classmethod
    def from_env(cls, provider: str | None = None, *, offline: bool = False) -> "Settings":
        # Offline operation must not depend on unrelated provider configuration.
        if offline:
            return cls(offline=True)
        selected = provider if provider is not None else os.getenv("SCRIBE_PROVIDER", "gemini")
        try:
            return cls(
                provider=selected,
                gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
                gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
                timeout=os.getenv("GEMINI_TIMEOUT_SECONDS", "180"),
            )
        except ValidationError as exc:
            raise StageError("check", "invalid extraction configuration", "environment") from exc
