import json
import subprocess
import sys
from copy import deepcopy

import pytest

from clinical_scribe.contracts import empty_note
from clinical_scribe.errors import StageError
from clinical_scribe.resolver import resolve

REGISTER = """kind,code,name,synonyms
diagnosis,K29.7,Gastritis,gastritis;tumbo kuwaka
diagnosis,K35.8,Appendicitis,appendix
drug,N02BE01,Paracetamol,panadol;acetaminophen
drug,A02BC01,Omeprazole,omez
procedure,PGP-EC-0330,Appendicectomy,appendectomy;appendix removal
allergen,ALG-EC-0003,Penicillins,penicillin
lab,LAB-EC-0412,Helicobacter pylori stool antigen,h pylori stool antigen
"""


def note(section, value, **extra):
    result = empty_note()
    result[section] = [
        {"value": value, "span": {"ref": "[00:00]", "text": value}, "confidence": 0.9, **extra}
    ]
    if section == "assessment":
        result[section][0].setdefault("certainty", "confirmed")
    return result


@pytest.mark.parametrize(
    "section,value,code",
    [
        ("assessment", "Probable gastritis.", "K29.7"),
        ("assessment", "tumbo kuwaka", "K29.7"),
        ("medication_history", "Na PANADOL sometimes.", "N02BE01"),
        ("past_surgical_history", "Appendix, 2019, at the county hospital.", "PGP-EC-0330"),
        ("allergies", "Penicillin.", "ALG-EC-0003"),
        ("plan", "check an H. pylori stool antigen.", "LAB-EC-0412"),
        ("plan", "start omeprazole 20 mg once daily", "A02BC01"),
    ],
)
def test_kind_aware_exact_lookup(section, value, code):
    original = note(section, value)
    before = deepcopy(original)
    result = resolve(original, REGISTER)[section][0]
    assert result["code"] == code
    assert result["status"] == "resolved"
    assert result["extraction_confidence"] == 0.9
    assert result["span"] == before[section][0]["span"]
    assert original == before


@pytest.mark.parametrize("certainty", ["probable", "differential", "confirmed"])
def test_uncertain_diagnoses_resolve_without_changing_certainty(certainty):
    result = resolve(note("assessment", "Gastritis", certainty=certainty), REGISTER)
    assert result["assessment"][0]["code"] == "K29.7"
    assert result["assessment"][0]["certainty"] == certainty


@pytest.mark.parametrize(
    "section,value,extra",
    [
        ("family_history", "My father had gastritis", {}),
        ("assessment", "My father had gastritis", {}),
        ("assessment", "Gastritis", {"attribution": "companion"}),
        ("assessment", "Gastritis", {"conflict": {"id": "one", "reason": "contradiction"}}),
        ("assessment", "Gastritis", {"kind": "considered_and_rejected"}),
        ("assessment", "No gastritis", {}),
        ("plan", "If needed start omeprazole", {}),
        ("medication_history", "Appendix", {}),
        ("past_surgical_history", "Appendicitis", {}),
    ],
)
def test_exclusions_and_wrong_kinds_abstain(section, value, extra):
    result = resolve(note(section, value, **extra), REGISTER)[section][0]
    assert result["code"] is None
    assert result["status"] == "unresolved"


def test_near_match_is_suggestion_not_forced_code():
    result = resolve(note("medication_history", "Panadolx"), REGISTER)["medication_history"][0]
    assert result["status"] == "unresolved"
    assert result["code"] is None
    assert result["alternatives"][0]["code"] == "N02BE01"


def test_near_match_rounding_cannot_authorize_a_code(monkeypatch):
    monkeypatch.setattr("clinical_scribe.resolver.SequenceMatcher.ratio", lambda self: 0.999999)
    result = resolve(note("medication_history", "Panadolx"), REGISTER)["medication_history"][0]
    assert result["code"] is None
    assert result["status"] == "unresolved"
    assert all(candidate["score"] < 1 for candidate in result["alternatives"])


def test_multiple_exact_matches_are_ambiguous_and_stable():
    register = REGISTER + "drug,X01AA01,Different medicine,panadol\n"
    original = note("medication_history", "Panadol")
    first = resolve(original, register)["medication_history"][0]
    assert first["status"] == "ambiguous"
    assert first["code"] is None
    rows = register.strip().splitlines()
    reordered = "\n".join([rows[0], *reversed(rows[1:])])
    assert first == resolve(original, reordered)["medication_history"][0]


@pytest.mark.parametrize(
    "register",
    [
        "kind,name,synonyms\ndrug,Medicine,alias\n",
        REGISTER + "diagnosis,N02BE01,Conflict,alias\n",
        "kind,code,name,synonyms\n",
        REGISTER + "drug,too,few\n",
    ],
)
def test_broken_register_fails_even_for_empty_note(register):
    with pytest.raises(StageError, match="resolve.*broken.csv"):
        resolve(empty_note(), register, "broken.csv")


def test_resolver_does_not_import_provider_or_use_network(tmp_path):
    # A fresh interpreter proves the resolver imports no HTTP/model module.
    script = """
import socket,sys
def forbidden(*a, **k):
    raise AssertionError('network used')
socket.socket = forbidden
from clinical_scribe.resolver import resolve
from clinical_scribe.contracts import empty_note
resolve(empty_note(), 'kind,code,name,synonyms\\ndrug,N02BE01,Paracetamol,panadol\\n')
assert 'clinical_scribe.providers' not in sys.modules
assert 'httpx' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_cli_resolve_output(tmp_path):
    input_path = tmp_path / "note.json"
    register_path = tmp_path / "register.csv"
    out = tmp_path / "resolved.json"
    input_path.write_text(json.dumps(note("medication_history", "Panadol")))
    register_path.write_text(REGISTER)
    result = subprocess.run(
        [
            sys.executable,
            "scribe",
            "resolve",
            "--note",
            str(input_path),
            "--register",
            str(register_path),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert json.loads(out.read_text())["medication_history"][0]["code"] == "N02BE01"
