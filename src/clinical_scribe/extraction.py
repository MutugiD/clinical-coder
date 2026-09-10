"""Evidence selection, deterministic rendering, and validated offline replay."""

import hashlib
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from clinical_scribe.config import Settings
from clinical_scribe.conflicts import conflict_groups
from clinical_scribe.contracts import empty_note, enforce
from clinical_scribe.errors import StageError
from clinical_scribe.evidence import ACK, Evidence, certainty, evidence
from clinical_scribe.loaders import parse_json, read_json
from clinical_scribe.output import canonical_bytes
from clinical_scribe.validation import reject_codes, validate


def transcript_hash(transcript: str) -> str:
    # Newline encoding does not change source turns; filenames have no role.
    normalized = transcript.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff\n")
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def render(items: list[Evidence], selections: list[dict]) -> dict:
    note = empty_note()
    conflicts = conflict_groups(items)
    seen = set()
    for selection in selections:
        index = selection["id"]
        if index in seen or index < 0 or index >= len(items):
            raise StageError("extract", "duplicate or unknown evidence selection")
        seen.add(index)
        item = items[index]
        sections = selection["sections"]
        if not sections or len(set(sections)) != len(sections):
            raise StageError("extract", "empty or duplicate section selection")
        for section in sections:
            if section not in item.sections:
                raise StageError("extract", "selected section is unsupported by source context")
            entry = {
                "value": item.text,
                "span": {"ref": item.turn.ref, "text": item.text},
                "confidence": 1.0,
                "attribution": item.turn.speaker.casefold(),
            }
            if item.context:
                entry["context_span"] = {"ref": item.context.ref, "text": item.context.text}
            if section == "assessment":
                entry["certainty"] = certainty(item.text)
            if item.rejected:
                entry["kind"] = "considered_and_rejected"
            if index in conflicts:
                entry["conflict"] = conflicts[index]
            if note[section] == "NOT_STATED":
                note[section] = []
            note[section].append(entry)
    return note


def offline_rules(transcript: str) -> dict:
    items = evidence(transcript)
    unknown = [
        e
        for e in items
        if e.turn.speaker == "PATIENT" and not e.sections and not ACK.fullmatch(e.text)
    ]
    if unknown:
        refs = ", ".join(sorted({e.turn.ref for e in unknown}))
        raise StageError("extract", f"offline rules cannot safely classify patient turns: {refs}")
    selections = [{"id": e.index, "sections": list(e.sections)} for e in items if e.sections]
    if not selections:
        raise StageError("extract", "no supported clinical facts; offline extraction abstained")
    note = render(items, selections)
    validate(transcript, note)
    return note


def replay(transcript: str) -> dict | None:
    manifest_path = Path("outputs/replay-manifest.json")
    if not manifest_path.exists():
        raise StageError("extract", "offline replay manifest is missing", str(manifest_path))
    manifest = read_json(manifest_path, "extract")
    enforce("replay_manifest", manifest, "extract")
    if manifest["transcript_hash"] != transcript_hash(transcript):
        return None
    note = read_json("outputs/note.json", "extract")
    if "sha256:" + hashlib.sha256(canonical_bytes(note)).hexdigest() != manifest["note_hash"]:
        raise StageError("extract", "offline note hash mismatch", "outputs/note.json")
    validate(transcript, note)
    return note


def extract(transcript: str, settings: Settings) -> tuple[dict, dict]:
    enforce("extract_request", {"transcript": transcript}, "extract")
    if settings.offline:
        cached = replay(transcript)
        note = cached if cached is not None else offline_rules(transcript)
        metadata = {
            "model": None,
            "prompt_hash": None,
            "mode": "replay" if cached is not None else "rules",
        }
    else:
        from clinical_scribe.providers import generate

        items = evidence(transcript)
        candidates = [
            {
                "id": e.index,
                "text": e.text,
                "speaker": e.turn.speaker,
                "allowed_sections": list(e.sections),
                "context": e.context.text if e.context else None,
            }
            for e in items
            if e.sections
        ]
        if not candidates:
            raise StageError("extract", "no supported clinical evidence candidates")
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "enum": [c["id"] for c in candidates]},
                            "sections": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"enum": list(empty_note())},
                            },
                        },
                        "required": ["id", "sections"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        }
        prompt = Path("prompts/extract.txt").read_text(encoding="utf-8")
        content, metadata = generate(settings, prompt, {"candidates": candidates}, schema)
        # Strip only an outer transport wrapper, never edit clinical selections.
        fenced = re.fullmatch(r"\s*```(?:json)?\s*\n(.*?)\n```\s*", content, re.S)
        selection = parse_json(fenced[1] if fenced else content, "extract", "provider response")
        reject_codes(selection, "extract")
        if not Draft202012Validator(schema).is_valid(selection):
            raise StageError("extract", "provider selection violates its schema")
        note = render(items, selection["items"])
        validate(transcript, note)
        metadata.update(
            mode="model", prompt_hash="sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        )
    enforce("extract_response", note, "extract")
    return note, metadata
