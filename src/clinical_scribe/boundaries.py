"""Shared schema-enforced processing boundaries for CLI, pipeline and HTTP."""

from clinical_scribe.config import Settings
from clinical_scribe.contracts import enforce
from clinical_scribe.errors import BoundaryOutputError, StageError
from clinical_scribe.extraction import extract
from clinical_scribe.knowledge import knowledge
from clinical_scribe.resolver import resolve
from clinical_scribe.validation import validate

STAGES = ("extract", "validate", "resolve", "knowledge")


def process(stage: str, payload: dict, settings: Settings | None = None) -> tuple[dict, dict]:
    if stage not in STAGES:
        raise StageError(stage, "unknown processing stage")
    enforce(stage + "_request", payload, stage)
    metadata = {}
    if stage == "extract":
        result, metadata = extract(payload["transcript"], settings or Settings.from_env())
    elif stage == "validate":
        result = validate(payload["transcript"], payload["note"])
    elif stage == "resolve":
        result = resolve(payload["note"], payload["register"])
    else:
        result = knowledge(payload["source"], payload.get("note"))
    try:
        enforce(stage + "_response", result, stage)
    except StageError as exc:
        raise BoundaryOutputError(stage, exc.message, "response") from exc
    return result, metadata
