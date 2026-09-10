import json
import subprocess
import sys

import pytest

from clinical_scribe.config import Settings
from clinical_scribe.contracts import empty_note, enforce
from clinical_scribe.errors import StageError
from clinical_scribe.loaders import parse_json, parse_register
from clinical_scribe.output import write_json
from clinical_scribe.transcript import parse_transcript


@pytest.mark.parametrize("text", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', "{"])
def test_invalid_json(text):
    with pytest.raises(StageError, match="invalid JSON"):
        parse_json(text, "validate")


@pytest.mark.parametrize(
    "text",
    [
        "",
        "kind,code,name,synonyms\n",
        "kind,name,synonyms\ndrug,Example,alias\n",
        "kind,code,name,synonyms\ndrug,X,Example,alias,extra\n",
        'kind,code,name,synonyms\ndrug,X,"unfinished\n',
        "kind,code,name,synonyms\ndrug,X,Example,alias\nlab,X,Test,test\n",
        "kind,code,name,synonyms\ndrug,,Example,alias\n",
    ],
)
def test_broken_registers(text):
    with pytest.raises(StageError, match="resolve: trial.csv"):
        parse_register(text, "trial.csv")


def test_valid_register_and_blank_lines():
    rows = parse_register("kind,code,name,synonyms\n\ndrug,X,Example,one;two\n")
    assert rows[0].synonyms == ("one", "two")
    assert rows[0].row == 3


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[00:01] OTHER: hello",
        "[00:70] PATIENT: hi",
        "[00:01] PATIENT: ",
        "[00:02] PATIENT: hi\n[00:01] DOCTOR: hello",
        "[00:01] PATIENT: hi\n[00:01] DOCTOR: hello",
    ],
)
def test_invalid_transcripts(text):
    with pytest.raises(StageError):
        parse_transcript(text)


def test_source_text_is_preserved():
    text = "Nina maumivu,  hapa."
    turns = parse_transcript("[02:07] PATIENT: " + text + "\r\n")
    assert turns[0].text == text


def test_output_is_atomic_and_unicode(tmp_path):
    output = tmp_path / "note.json"
    write_json(output, {"value": "maumivu — mild"}, "extract")
    assert json.loads(output.read_text(encoding="utf8"))["value"] == "maumivu — mild"
    assert len(list(tmp_path.iterdir())) == 1


def test_failed_serialization_preserves_previous_output(tmp_path):
    output = tmp_path / "note.json"
    output.write_text('{"previous":true}', encoding="utf8")
    with pytest.raises(StageError, match="cannot write output"):
        write_json(output, {"confidence": float("nan")}, "extract")
    assert json.loads(output.read_text()) == {"previous": True}


def test_invalid_utf8_cli(tmp_path):
    transcript = tmp_path / "bad.txt"
    transcript.write_bytes(b"\xff\xfe\x00")
    result = subprocess.run(
        [
            sys.executable,
            "scribe",
            "extract",
            "--transcript",
            str(transcript),
            "--out",
            str(tmp_path / "note.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "bad.txt" in result.stderr and "UTF-8" in result.stderr
    assert result.stdout == ""


def test_required_shape_and_confidence():
    note = empty_note()
    enforce("note", note, "validate")
    note["assessment"] = [
        {
            "value": "possible condition",
            "span": {"ref": "[00:00]", "text": "condition"},
            "confidence": 1.1,
        }
    ]
    with pytest.raises(StageError):
        enforce("note", note, "validate")


def test_config_is_explicit(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "chosen-model")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "15")
    assert Settings.from_env().model == "chosen-model"
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "-1")
    with pytest.raises(StageError, match="configuration"):
        Settings.from_env()


def test_missing_file_cli(tmp_path):
    missing = tmp_path / "missing.txt"
    result = subprocess.run(
        [
            sys.executable,
            "scribe",
            "extract",
            "--transcript",
            str(missing),
            "--out",
            str(tmp_path / "note.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert "extract" in result.stderr and "missing.txt" in result.stderr
    assert not (tmp_path / "note.json").exists()


def test_missing_argument_cli():
    result = subprocess.run(
        [sys.executable, "scribe", "resolve"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "--register" in result.stderr
