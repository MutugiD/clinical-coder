"""Independent source, numeric, attribution, and scope validation."""

import re
from typing import Any

from clinical_scribe.conflicts import conflict_groups
from clinical_scribe.contracts import enforce
from clinical_scribe.errors import StageError
from clinical_scribe.evidence import Evidence, certainty, evidence
from clinical_scribe.normalization import normalize

CODE = re.compile(r"(?:[A-Z]\d{2}[A-Z]{2}\d{2}|(?:LAB|PGP|ALG)-EC-\d{4}|[A-Z]\d{2}(?:\.\d)?)")


def reject_codes(value: Any, stage: str = "validate") -> None:
    if isinstance(value, str) and CODE.search(value):
        raise StageError(stage, "code-like string is forbidden in a clinical note")
    if isinstance(value, dict):
        for key, item in value.items():
            reject_codes(key, stage)
            reject_codes(item, stage)
    elif isinstance(value, list):
        for item in value:
            reject_codes(item, stage)


def primary_evidence(span: dict, items: list[Evidence]) -> list[Evidence]:
    turns = [item for item in items if item.turn.ref == span["ref"]]
    if not turns or span["text"] not in turns[0].turn.text:
        raise StageError("validate", "primary span is not verbatim at its timestamp")
    exact = [item for item in turns if normalize(item.text) == normalize(span["text"])]
    if exact:
        return exact
    # A full turn is supported only when every clause is valid in the chosen section.
    if span["text"] == turns[0].turn.text:
        return turns
    raise StageError("validate", "span truncates a supported clause or its clinical qualifiers")


def validate(transcript: str, note: dict) -> dict:
    enforce("validate_request", {"transcript": transcript, "note": note}, "validate")
    reject_codes(note)
    items = evidence(transcript, "validate")
    source_turns = {item.turn.ref: item.turn for item in items}
    conflicts = conflict_groups(items)
    recorded = set()
    for section, elements in note.items():
        if elements == "NOT_STATED":
            continue
        for entry in elements:
            matched = primary_evidence(entry["span"], items)
            if normalize(entry["value"]) != normalize(entry["span"]["text"]):
                raise StageError(
                    "validate", "value changes source wording, numbers, units, or order"
                )
            if context := entry.get("context_span"):
                turn = source_turns.get(context["ref"])
                if not turn or context["text"] not in turn.text:
                    raise StageError("validate", "context span is not a real source quotation")
            for item in matched:
                speaker = item.turn.speaker.casefold()
                if "attribution" in entry and entry["attribution"] != speaker:
                    raise StageError("validate", "attribution disagrees with source speaker")
                companion = speaker == "companion" and entry.get("attribution") == "companion"
                if not companion and section not in item.sections:
                    raise StageError("validate", f"source does not support section {section}")
                if speaker == "companion" and not companion:
                    raise StageError("validate", "companion statement recorded as patient fact")
                if item.rejected != (entry.get("kind") == "considered_and_rejected"):
                    raise StageError(
                        "validate", "thinking-aloud/rejection marker disagrees with source"
                    )
                if section == "assessment" and entry["certainty"] != certainty(item.text):
                    raise StageError("validate", "assessment certainty disagrees with source")
                expected = conflicts.get(item.index)
                if expected and entry.get("conflict") != expected:
                    raise StageError(
                        "validate", "contradictory source requires shared conflict markers"
                    )
                if entry.get("conflict") and not expected:
                    raise StageError(
                        "validate", "conflict marker lacks supported contradictory evidence"
                    )
                recorded.add(item.index)
    if conflicts.keys() - recorded:
        raise StageError("validate", "a contradictory source statement was omitted")
    result = {"valid": True}
    enforce("validate_response", result, "validate")
    return result
