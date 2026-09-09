"""Canonical serialization and atomic artifact replacement."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from clinical_scribe.errors import StageError


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def write_json(path: str | Path, value: Any, stage: str) -> None:
    target = Path(path)
    temporary = None
    try:
        data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=target.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(data)
        os.replace(temporary, target)
    except (OSError, ValueError) as exc:
        raise StageError(stage, f"cannot write output: {exc}", str(path)) from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
