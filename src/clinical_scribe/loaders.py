"""Strict file, JSON, and catalogue parsing."""

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clinical_scribe.errors import StageError


def read_text(path: str | Path, stage: str) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise StageError(stage, f"cannot read UTF-8 input: {exc}", str(path)) from exc
    if not text.strip():
        raise StageError(stage, "empty input", str(path))
    return text


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def parse_json(text: str, stage: str, source: str = "JSON") -> Any:
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise StageError(stage, f"invalid JSON: {exc}", source) from exc


def read_json(path: str | Path, stage: str) -> Any:
    return parse_json(read_text(path, stage), stage, str(path))


@dataclass(frozen=True)
class RegisterEntry:
    kind: str
    code: str
    name: str
    synonyms: tuple[str, ...]
    row: int


def parse_register(text: str, source: str = "register") -> list[RegisterEntry]:
    required = {"kind", "code", "name", "synonyms"}
    kinds = {"diagnosis", "drug", "lab", "procedure", "allergen"}
    reader = csv.reader(io.StringIO(text), strict=True)
    rows: list[RegisterEntry] = []
    codes: dict[str, str] = {}
    try:
        header = next(reader, [])
        if len(set(header)) != len(header) or not required.issubset(header):
            raise StageError("resolve", "missing or duplicate required CSV columns", source)
        for row in reader:
            if not row:
                continue
            if len(row) != len(header):
                raise StageError("resolve", f"row {reader.line_num}: incorrect field count", source)
            item = dict(zip(header, (cell.strip() for cell in row), strict=True))
            if not all(item[k] for k in ("kind", "code", "name")):
                raise StageError("resolve", f"row {reader.line_num}: empty required value", source)
            if item["kind"] not in kinds:
                raise StageError("resolve", f"row {reader.line_num}: unknown kind", source)
            if item["code"] in codes:
                previous = codes[item["code"]]
                raise StageError(
                    "resolve",
                    f"row {reader.line_num}: duplicate code {item['code']} ({previous}, "
                    f"{item['kind']})",
                    source,
                )
            codes[item["code"]] = item["kind"]
            rows.append(RegisterEntry(
                kind=item["kind"], code=item["code"], name=item["name"],
                synonyms=tuple(s.strip() for s in item["synonyms"].split(";") if s.strip()),
                row=reader.line_num,
            ))
    except csv.Error as exc:
        raise StageError("resolve", f"row {reader.line_num}: malformed CSV: {exc}", source) from exc
    if not rows:
        raise StageError("resolve", "register contains no entries", source)
    return rows
