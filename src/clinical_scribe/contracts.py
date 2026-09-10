"""Offline JSON Schema registry shared by local and HTTP boundaries."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from clinical_scribe.errors import StageError


@lru_cache
def schema_registry() -> tuple[dict, Registry]:
    try:
        root = json.loads(Path("schemas/contracts.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(root)
        registry = Registry().with_resource(root["$id"], Resource.from_contents(root))
        return root, registry
    except (OSError, ValueError) as exc:
        raise StageError(
            "check", "run from repository root; schemas unavailable", "schemas"
        ) from exc


def enforce(name: str, payload: Any, stage: str) -> None:
    root, registry = schema_registry()
    if name not in root["$defs"]:
        raise StageError(stage, f"unknown contract: {name}", "schemas")
    validator = Draft202012Validator({"$ref": root["$id"] + "#/$defs/" + name}, registry=registry)
    error = next(validator.iter_errors(payload), None)
    if error is not None:
        path = ".".join(map(str, error.absolute_path)) or "$"
        # Avoid echoing the full clinical payload included in library error strings.
        raise StageError(stage, f"schema violation at {path}: {error.validator}", name)


def empty_note() -> dict:
    root, _ = schema_registry()
    return dict.fromkeys(root["$defs"]["note"]["required"], "NOT_STATED")
