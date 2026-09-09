"""Explicit extraction configuration; no provider fallback."""

import os

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

from clinical_scribe.errors import StageError


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: HttpUrl = HttpUrl("http://localhost:11434")
    model: str = Field(default="glm-5.2:cloud", min_length=1)
    timeout: float = Field(default=180, gt=0, le=600)

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            return cls(
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                model=os.getenv("OLLAMA_MODEL", "glm-5.2:cloud"),
                timeout=os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"),
            )
        except ValidationError as exc:
            raise StageError("check", "invalid Ollama configuration", "environment") from exc

    def endpoint(self, path: str) -> str:
        return str(self.base_url).rstrip("/") + path
