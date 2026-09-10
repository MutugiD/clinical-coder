import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from clinical_scribe.contracts import enforce
from clinical_scribe.errors import ProviderError, StageError
from clinical_scribe.extraction import offline_rules
from clinical_scribe.pipeline import digest, run_pipeline

FIXTURES = Path(__file__).parent / "fixtures"
REGISTER = "kind,code,name,synonyms\ndrug,N02BE01,Paracetamol,panadol\n"


@pytest.fixture
def inputs(tmp_path):
    transcript = tmp_path / "consultation with spaces.txt"
    transcript.write_text((FIXTURES / "alternate_consultation.txt").read_text())
    register = tmp_path / "register with spaces.csv"
    register.write_text(REGISTER)
    source = tmp_path / "guideline with spaces.txt"
    source.write_text((FIXTURES / "alternate_guideline.txt").read_text())
    return transcript, register, source


def logs(directory):
    rows = [json.loads(line) for line in (directory / "run_log.jsonl").read_text().splitlines()]
    for row in rows:
        enforce("stage_log", row, "test")
        assert datetime.fromisoformat(row["timestamp"]).tzinfo
    return rows


def test_full_cli_pipeline_with_spaces_and_actual_hashes(inputs, tmp_path):
    transcript, register, source = inputs
    output = tmp_path / "pipeline results"
    result = subprocess.run(
        [
            sys.executable,
            "scribe",
            "pipeline",
            "--transcript",
            str(transcript),
            "--register",
            str(register),
            "--source",
            str(source),
            "--out",
            str(output),
            "--offline",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    rows = logs(output)
    assert [r["stage"] for r in rows] == ["extract", "validate", "resolve", "knowledge"]
    assert all(r["status"] == "ok" for r in rows)
    assert len({r["run_id"] for r in rows}) == 1
    assert rows[0]["mode"] == "rules" and rows[0]["model"] is None
    note = json.loads((output / "note.json").read_text())
    resolved = json.loads((output / "resolved.json").read_text())
    knowledge = json.loads((output / "knowledge.json").read_text())
    expected_inputs = [
        {"transcript": transcript.read_text()},
        {"transcript": transcript.read_text(), "note": note},
        {"note": note, "register": register.read_text()},
        {"source": source.read_text(), "note": note},
    ]
    for row, payload, response in zip(
        rows, expected_inputs, [note, {"valid": True}, resolved, knowledge], strict=True
    ):
        assert row["input_hash"] == digest(payload)
        assert row["output_hash"] == digest(response)
    assert resolved["medication_history"][0]["code"] == "N02BE01"


@pytest.mark.parametrize(
    "broken",
    [
        "kind,name,synonyms\ndrug,Medicine,alias\n",
        "",
        REGISTER + "diagnosis,N02BE01,Conflict,alias\n",
        REGISTER + 'drug,X,"unterminated\n',
    ],
)
def test_all_broken_registers_fail_at_resolve_with_file_and_logs(inputs, tmp_path, broken):
    transcript, register, source = inputs
    register.write_text(broken)
    output = tmp_path / "broken-run"
    result = subprocess.run(
        [
            sys.executable,
            "scribe",
            "pipeline",
            "--offline",
            "--transcript",
            str(transcript),
            "--register",
            str(register),
            "--source",
            str(source),
            "--out",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert "resolve" in result.stderr and str(register) in result.stderr
    assert [r["status"] for r in logs(output)] == ["ok", "ok", "failed", "skipped"]
    assert not (output / "resolved.json").exists()
    assert not (output / "knowledge.json").exists()


def test_invalid_intermediate_note_fails_validation_before_publication(
    inputs, tmp_path, monkeypatch
):
    transcript, register, source = inputs
    note = offline_rules(transcript.read_text())
    note["vitals"][0]["value"] = "Temperature is 99."
    monkeypatch.setattr("clinical_scribe.boundaries.extract", lambda *a: (note, {}))
    output = tmp_path / "invalid-note"
    with pytest.raises(StageError, match="validate"):
        run_pipeline(str(transcript), str(register), str(source), str(output), offline=True)
    assert [r["status"] for r in logs(output)] == ["ok", "failed", "skipped", "skipped"]
    assert not (output / "note.json").exists()


def test_provider_failure_is_logged_without_secret_or_fallback(inputs, tmp_path, monkeypatch):
    def fail(*args):
        raise ProviderError("extract", "gemini HTTP 503")

    monkeypatch.setattr("clinical_scribe.providers.generate", fail)
    monkeypatch.setenv("GEMINI_API_KEY", "private-test-key")
    output = tmp_path / "provider-failure"
    with pytest.raises(StageError, match="extract"):
        run_pipeline(*map(str, inputs), str(output), provider="gemini")
    rows = logs(output)
    assert [r["status"] for r in rows] == ["failed", "skipped", "skipped", "skipped"]
    assert rows[0]["model"].startswith("gemini/")
    assert rows[0]["prompt_hash"].startswith("sha256:")
    assert "private-test-key" not in (output / "run_log.jsonl").read_text()
    assert all(row["output_hash"] is None for row in rows)


def test_missing_input_and_invalid_config_are_audited(inputs, tmp_path, monkeypatch):
    transcript, register, source = inputs
    transcript.unlink()
    output = tmp_path / "missing"
    with pytest.raises(StageError, match="extract"):
        run_pipeline(*map(str, inputs), str(output), offline=True)
    assert logs(output)[0]["input_hash"] == digest({"unavailable_input": str(transcript)})
    transcript.write_text("[00:00] NURSE: Pulse 80.")
    monkeypatch.setenv("SCRIBE_PROVIDER", "invalid")
    with pytest.raises(StageError, match="configuration"):
        run_pipeline(*map(str, inputs), str(output))
    assert len(logs(output)) == 8
    assert len({row["run_id"] for row in logs(output)}) == 2


def test_failure_preserves_prior_artifacts_but_new_run_records_failure(inputs, tmp_path):
    output = tmp_path / "repeat"
    run_pipeline(*map(str, inputs), str(output), offline=True)
    before = (output / "resolved.json").read_bytes()
    inputs[1].write_text("bad")
    with pytest.raises(StageError):
        run_pipeline(*map(str, inputs), str(output), offline=True)
    assert (output / "resolved.json").read_bytes() == before
    assert [row["status"] for row in logs(output)[-4:]] == ["ok", "ok", "failed", "skipped"]


def test_output_must_not_overwrite_input(inputs, tmp_path):
    output = tmp_path / "collision"
    output.mkdir()
    transcript = output / "note.json"
    transcript.write_text(inputs[0].read_text())
    before = transcript.read_bytes()
    with pytest.raises(StageError, match="overwrite"):
        run_pipeline(str(transcript), str(inputs[1]), str(inputs[2]), str(output), offline=True)
    assert transcript.read_bytes() == before


def test_knowledge_failure_is_terminal_and_identifies_source(inputs, tmp_path):
    inputs[2].write_text("unsupported guideline")
    output = tmp_path / "bad-guideline"
    with pytest.raises(StageError, match="knowledge") as error:
        run_pipeline(*map(str, inputs), str(output), offline=True)
    assert str(inputs[2]) in str(error.value)
    assert [row["status"] for row in logs(output)] == ["ok", "ok", "ok", "failed"]


def test_output_write_failure_is_not_reported_successful(inputs, tmp_path, monkeypatch):
    def fail(path, value, stage):
        raise StageError(stage, "cannot write output", str(path))

    monkeypatch.setattr("clinical_scribe.pipeline.write_json", fail)
    output = tmp_path / "write-failure"
    with pytest.raises(StageError, match="cannot write output"):
        run_pipeline(*map(str, inputs), str(output), offline=True)
    assert [row["status"] for row in logs(output)] == ["ok", "failed", "skipped", "skipped"]


@pytest.mark.parametrize(
    "wording,certainty",
    [
        ("Assessment: Gastritis.", "confirmed"),
        ("Most likely gastritis.", "probable"),
        ("Possible gastritis.", "differential"),
    ],
)
def test_pipeline_preserves_conflict_and_unrelated_diagnosis_certainty(
    inputs, tmp_path, wording, certainty
):
    inputs[0].write_text(
        "[00:00] DOCTOR: Any medicines?\n"
        "[00:04] PATIENT: I take diclofenac every day.\n"
        "[00:08] PATIENT: I don't take diclofenac.\n"
        f"[00:12] DOCTOR: {wording}"
    )
    inputs[1].write_text(
        "kind,code,name,synonyms\ndrug,M01AB05,Diclofenac,voltaren\n"
        "diagnosis,K29.7,Gastritis,gastritis\n"
    )
    output = tmp_path / "conflict-pipeline"
    run_pipeline(*map(str, inputs), str(output), offline=True)
    resolved = json.loads((output / "resolved.json").read_text())
    first, second = resolved["medication_history"]
    assert first["conflict"] == second["conflict"]
    assert first["code"] is second["code"] is None
    assessment = resolved["assessment"][0]
    assert assessment["code"] == "K29.7" and assessment["certainty"] == certainty
    assert all(row["status"] == "ok" for row in logs(output))
