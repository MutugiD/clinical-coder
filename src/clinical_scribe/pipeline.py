"""Ordered in-process stages with durable terminal audit records."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from clinical_scribe.boundaries import STAGES, process
from clinical_scribe.config import Settings
from clinical_scribe.contracts import enforce
from clinical_scribe.errors import StageError
from clinical_scribe.loaders import read_text
from clinical_scribe.output import canonical_bytes, write_json


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def append_record(path: Path, record: dict) -> None:
    enforce("stage_log", record, "pipeline")
    try:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise StageError("pipeline", "cannot append audit log", str(path)) from exc


def run_pipeline(
    transcript_path: str,
    register_path: str,
    source_path: str,
    out: str,
    provider: str | None = None,
    offline: bool = False,
) -> None:
    directory = Path(out)
    inputs = {Path(p).resolve() for p in (transcript_path, register_path, source_path)}
    targets = {
        directory / name
        for name in ("note.json", "resolved.json", "knowledge.json", "run_log.jsonl")
    }
    if any(target.resolve() in inputs for target in targets):
        raise StageError("pipeline", "output artifact would overwrite an input", out)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StageError("pipeline", "cannot create output directory", out) from exc
    run_id = str(uuid4())
    failure = None
    transcript = note = None
    paths = {
        "extract": transcript_path,
        "validate": transcript_path,
        "resolve": register_path,
        "knowledge": source_path,
    }
    for stage in STAGES:
        record = {
            "run_id": run_id,
            "stage": stage,
            "timestamp": "",
            "status": "skipped",
            "input_hash": None,
            "output_hash": None,
            "model": None,
            "prompt_hash": None,
            "message": "skipped after an earlier stage failed",
        }
        if failure is None:
            # If loading fails, this explicitly tagged descriptor is hashed instead of content.
            record["input_hash"] = digest({"unavailable_input": str(paths[stage])})
            try:
                settings = None
                if stage == "extract":
                    transcript = read_text(transcript_path, stage)
                    payload = {"transcript": transcript}
                elif stage == "validate":
                    payload = {"transcript": transcript, "note": note}
                elif stage == "resolve":
                    payload = {"note": note, "register": read_text(register_path, stage)}
                else:
                    payload = {"source": read_text(source_path, stage), "note": note}
                record["input_hash"] = digest(payload)
                if stage == "extract":
                    settings = Settings.from_env(provider, offline=offline)
                    record["mode"] = "offline" if offline else "model"
                    if not offline:
                        model = (
                            settings.model
                            if settings.provider == "ollama"
                            else settings.gemini_model
                        )
                        record["model"] = settings.provider + "/" + model
                        prompt = read_text("prompts/extract.txt", stage)
                        record["prompt_hash"] = (
                            "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()
                        )
                result, metadata = process(stage, payload, settings)
                if stage == "extract":
                    note = result
                    record.update(
                        {k: metadata[k] for k in ("model", "prompt_hash", "mode") if k in metadata}
                    )
                    record["provider_metadata"] = metadata
                elif stage == "validate":
                    write_json(directory / "note.json", note, stage)
                else:
                    filename = "resolved.json" if stage == "resolve" else "knowledge.json"
                    write_json(directory / filename, result, stage)
                record.update(status="ok", output_hash=digest(result), message="completed")
            except Exception as exc:
                message = (
                    exc.message if isinstance(exc, StageError) else "unexpected internal failure"
                )
                if isinstance(exc, StageError) and exc.source not in {"input", paths[stage]}:
                    message = f"{exc.source}: {message}"
                failure = StageError(stage, message, str(paths[stage]))
                record.update(status="failed", message=str(failure), output_hash=None)
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        append_record(directory / "run_log.jsonl", record)
    if failure:
        raise failure
