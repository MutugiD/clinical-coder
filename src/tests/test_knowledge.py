import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from clinical_scribe.contracts import empty_note
from clinical_scribe.errors import StageError
from clinical_scribe.knowledge import knowledge, verify_knowledge

SOURCE = (Path(__file__).parent / "fixtures" / "alternate_guideline.txt").read_text()


def test_source_only_rules_and_citations():
    result = knowledge(SOURCE)
    assert [row["type"] for row in result["rows"]] == [
        "drug_class_rule",
        "drug_class_rule",
        "test_constraint",
        "red_flag",
        "red_flag",
    ]
    assert (
        result["rows"][0]["fields"]["action"] == "receive PPI co-prescription for gastroprotection"
    )
    assert result["rows"][1]["fields"]["duration"] == "three weeks"
    assert result["rows"][2]["fields"]["lookback_interval"] == "one week"
    assert len(result["not_in_corpus"]) == 2
    assert "The plan mentions" not in result["prose"]
    assert len(result["prose"].split()) < 200
    for row in result["rows"]:
        assert row["source"] == "Synthetic Clinic Guideline"
        assert row["section"] == "6.1"
        assert row["page"] == 28
        assert row["quote"] in SOURCE


def test_optional_note_changes_only_prose():
    note = empty_note()
    note["plan"] = [
        {
            "value": "Check stool antigen.",
            "span": {"ref": "[00:00]", "text": "Check stool antigen."},
            "confidence": 1.0,
        }
    ]
    baseline = knowledge(SOURCE)
    contextual = knowledge(SOURCE, note)
    assert baseline["rows"] == contextual["rows"]
    assert baseline["not_in_corpus"] == contextual["not_in_corpus"]
    assert "The plan mentions a stool-antigen test" in contextual["prose"]
    assert len(contextual["prose"].split()) < 200
    assert "The plan mentions" not in knowledge(SOURCE, empty_note())["prose"]


@pytest.mark.parametrize("dose", ["20 mg", "20mg", "twenty milligrams", ".5 mg"])
def test_explicit_source_dose_removes_only_dose_gap(dose):
    result = knowledge(SOURCE.replace("standard dose", dose))
    assert result["rows"][1]["fields"]["dose"] == dose
    assert len(result["not_in_corpus"]) == 1
    assert "under 18" in result["not_in_corpus"][0]


def test_age_guidance_is_source_derived():
    result = knowledge(SOURCE.replace("Patients with persistent symptoms", "Patients under 18"))
    assert len(result["not_in_corpus"]) == 1
    assert "milligrams" in result["not_in_corpus"][0]


def test_alarm_age_does_not_supply_treatment_guidance():
    result = knowledge(SOURCE.replace("persistent vomiting, dysphagia", "age under 18"))
    assert any("under 18" in gap for gap in result["not_in_corpus"])


def test_another_class_dose_does_not_supply_ppi_dose():
    source = SOURCE.replace("A proton pump inhibitor (PPI) at standard dose", "A NSAID at 20 mg")
    result = knowledge(source)
    assert any("PPI dose" in gap for gap in result["not_in_corpus"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("quote", "An invented recommendation."),
        ("source", "Another source"),
        ("section", "9.2"),
        ("page", 99),
        ("fields", {"dose": "200 mg", "action": "increase dose"}),
    ],
)
def test_tampered_citations_and_fields_fail(field, value):
    result = knowledge(SOURCE)
    result["rows"][0][field] = value
    with pytest.raises(StageError):
        verify_knowledge(SOURCE, result)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "gaps", "prose"])
def test_incomplete_or_invalid_output_fails(mutation):
    result = knowledge(SOURCE)
    if mutation == "missing":
        result["rows"].pop()
    elif mutation == "duplicate":
        result["rows"].append(deepcopy(result["rows"][0]))
    elif mutation == "gaps":
        result["not_in_corpus"] = []
    else:
        result["prose"] = "word " * 200
    with pytest.raises(StageError):
        verify_knowledge(SOURCE, result)


@pytest.mark.parametrize(
    "source",
    [
        "",
        "Unsupported free text",
        SOURCE.replace("Section 6.1", "Section 8.1"),
        SOURCE.replace("page 28", "page 0"),
        SOURCE + "\nAn unsupported instruction follows.",
        SOURCE + "\n7.2 Another section.",
        SOURCE.replace("persistent vomiting, dysphagia", "persistent vomiting,, dysphagia"),
    ],
)
def test_unsupported_source_fails_clearly(source):
    with pytest.raises(StageError, match="knowledge"):
        knowledge(source)


def test_cli_source_only_and_failure_preserves_output(tmp_path):
    source = tmp_path / "guideline.txt"
    source.write_text(SOURCE)
    out = tmp_path / "knowledge.json"
    command = [sys.executable, "scribe", "knowledge", "--source", str(source), "--out", str(out)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    before = out.read_bytes()
    assert json.loads(before)["rows"]
    source.write_text("Unsupported source")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert "knowledge" in result.stderr
    assert str(source) in result.stderr
    assert result.stdout == ""
    assert out.read_bytes() == before


def test_knowledge_does_not_import_provider_or_use_network():
    script = """
import socket,sys
from pathlib import Path
def forbidden(*a, **k):
    raise AssertionError('network used')
socket.socket = forbidden
from clinical_scribe.knowledge import knowledge
knowledge(Path('src/tests/fixtures/alternate_guideline.txt').read_text())
assert 'clinical_scribe.providers' not in sys.modules
assert 'httpx' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
