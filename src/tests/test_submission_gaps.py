"""Independent acceptance examples from the final submission review."""

import json
import subprocess
import sys
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from clinical_scribe.config import Settings
from clinical_scribe.errors import StageError
from clinical_scribe.extraction import extract, offline_rules
from clinical_scribe.resolver import resolve
from clinical_scribe.services import create_app
from clinical_scribe.validation import validate

REGISTER = (
    "kind,code,name,synonyms\n"
    "diagnosis,K29.7,Gastritis,gastritis\n"
    "allergen,ALG-EC-0003,Penicillins,penicillin\n"
    "drug,M01AB05,Diclofenac,voltaren\n"
    "drug,N02BE01,Paracetamol,panadol\n"
)


@pytest.mark.parametrize("separator", [" ", "\n[00:03] DOCTOR: "])
def test_rejection_continuation_excludes_previous_hypothesis(separator):
    text = "[00:00] DOCTOR: I think gastritis." + separator + "But no."
    note = offline_rules(text)
    assert all(e["kind"] == "considered_and_rejected" for e in note["assessment"])
    assert all(e["code"] is None for e in resolve(note, REGISTER)["assessment"])
    del note["assessment"][0]["kind"]
    with pytest.raises(StageError):
        validate(text, note)


def test_allergy_contradiction_stays_visible_and_uncoded():
    text = (
        "[00:00] DOCTOR: Any allergies?\n"
        "[00:03] PATIENT: Penicillin allergy.\n"
        "[00:06] PATIENT: No penicillin allergy."
    )
    note = offline_rules(text)
    a, b = note["allergies"]
    assert a["conflict"] == b["conflict"]
    assert all(e["code"] is None for e in resolve(note, REGISTER)["allergies"])
    del b["conflict"]
    with pytest.raises(StageError):
        validate(text, note)


def test_mixed_polarity_conflict_is_per_concept():
    text = (
        "[00:00] DOCTOR: Any cough or fever?\n"
        "[00:03] PATIENT: No cough but fever.\n"
        "[00:06] PATIENT: No fever."
    )
    note = offline_rules(text)
    positive = note["history_of_presenting_illness"][0]
    cough, negative = note["review_of_systems"]
    assert positive["value"] == "fever."
    assert positive["conflict"] == negative["conflict"]
    assert "conflict" not in cough
    assert validate(text, note)["valid"]


def test_unasked_negative_is_hpi_and_cannot_move_to_ros():
    text = "[00:00] DOCTOR: Any vomiting?\n[00:03] PATIENT: No vomiting. No cough."
    note = offline_rules(text)
    assert [e["value"] for e in note["review_of_systems"]] == ["No vomiting."]
    assert note["history_of_presenting_illness"][0]["value"] == "No cough."
    note["review_of_systems"].extend(note["history_of_presenting_illness"])
    note["history_of_presenting_illness"] = "NOT_STATED"
    with pytest.raises(StageError):
        validate(text, note)


def test_direct_diagnosis_not_silently_omitted():
    note = offline_rules("[00:00] NURSE: Pulse 70.\n[00:03] DOCTOR: You have gastritis.")
    assert note["assessment"][0]["value"] == "You have gastritis."
    assert note["assessment"][0]["certainty"] == "confirmed"


def test_two_medicines_are_independent_elements():
    text = "[00:00] DOCTOR: Any medicines?\n[00:03] PATIENT: I take diclofenac and Panadol."
    note = offline_rules(text)
    entries = resolve(note, REGISTER)["medication_history"]
    assert [e["code"] for e in entries] == ["M01AB05", "N02BE01"]
    assert all(e["span"]["text"] in text for e in entries)
    assert validate(text, note)["valid"]


@pytest.mark.parametrize(
    "text,selection",
    [
        (
            "[00:00] NURSE: Pulse 70.\n[00:03] DOCTOR: You have gastritis.",
            {"items": [{"id": 0, "sections": ["vitals"]}]},
        ),
        (
            "[00:00] DOCTOR: What brings you in?\n[00:03] PATIENT: Pain for three weeks.",
            {"items": [{"id": 1, "sections": ["chief_complaint"]}]},
        ),
    ],
)
def test_model_cannot_omit_required_evidence(monkeypatch, text, selection):
    monkeypatch.setattr(
        "clinical_scribe.providers.generate", lambda *a: (json.dumps(selection), {})
    )
    with pytest.raises(StageError, match="omitted|required|complete"):
        extract(text, Settings())


def test_rejection_tamper_rejected_by_cli_and_http(tmp_path):
    text = "[00:00] DOCTOR: I think gastritis. But no."
    good = offline_rules(text)
    bad = deepcopy(good)
    bad["assessment"][0].pop("kind", None)
    transcript = tmp_path / "consultation with spaces.txt"
    transcript.write_text(text)
    note_path = tmp_path / "note.json"
    with TestClient(create_app("validate")) as client:
        for note, status in [(good, 200), (bad, 422)]:
            assert (
                client.post("/process", json={"transcript": text, "note": note}).status_code
                == status
            )
            note_path.write_text(json.dumps(note))
            result = subprocess.run(
                [
                    sys.executable,
                    "scribe",
                    "validate",
                    "--transcript",
                    str(transcript),
                    "--note",
                    str(note_path),
                ],
                capture_output=True,
                text=True,
            )
            assert (result.returncode == 0) == (status == 200)
            if status != 200:
                assert result.stderr


def test_explicitly_different_periods_do_not_conflict():
    text = (
        "[00:00] DOCTOR: Any cough?\n"
        "[00:03] PATIENT: Cough yesterday.\n"
        "[00:06] PATIENT: No cough today."
    )
    note = offline_rules(text)
    assert all(
        "conflict" not in e
        for entries in note.values()
        if isinstance(entries, list)
        for e in entries
    )


@pytest.mark.parametrize(
    "statement",
    [
        "Actually, I meant Panadol.",
        "I take diclofenac and Panadol 500 mg daily.",
        "I do not take diclofenac and Panadol.",
    ],
)
def test_unsupported_medication_scope_fails_explicitly(statement):
    text = "[00:00] DOCTOR: Any medicines?\n[00:03] PATIENT: " + statement
    with pytest.raises(StageError, match="unsupported"):
        offline_rules(text)


def test_unknown_clinician_statement_cannot_silently_disappear(monkeypatch):
    text = "[00:00] NURSE: Pulse 70.\n[00:03] DOCTOR: An unfamiliar clinical assertion."
    with pytest.raises(StageError, match="cannot safely classify"):
        offline_rules(text)
    monkeypatch.setattr(
        "clinical_scribe.providers.generate", lambda *a: pytest.fail("must abstain before model")
    )
    with pytest.raises(StageError, match="cannot safely classify"):
        extract(text, Settings())


def test_positive_diagnosis_not_rejected_by_unrelated_later_statement():
    text = "[00:00] DOCTOR: You have gastritis.\n[00:03] DOCTOR: I considered reflux but no."
    resolved = resolve(offline_rules(text), REGISTER)
    assert resolved["assessment"][0]["code"] == "K29.7"
    assert resolved["assessment"][1]["code"] is None


def test_now_does_not_hide_an_opposing_current_medication_statement():
    text = (
        "[00:00] DOCTOR: Any medicines?\n"
        "[00:03] PATIENT: I take diclofenac.\n"
        "[00:06] PATIENT: I do not take diclofenac now."
    )
    first, second = offline_rules(text)["medication_history"]
    assert first["conflict"] == second["conflict"]


def test_general_allergy_denial_conflicts_with_named_allergy():
    text = (
        "[00:00] DOCTOR: Any allergies?\n"
        "[00:03] PATIENT: Penicillin allergy.\n"
        "[00:06] PATIENT: No known allergies."
    )
    note = offline_rules(text)
    first, second = note["allergies"]
    assert first["conflict"] == second["conflict"]
    assert all(e["code"] is None for e in resolve(note, REGISTER)["allergies"])


def test_overlapping_conflicts_keep_a_shared_group():
    text = (
        "[00:00] DOCTOR: Any cough or fever?\n"
        "[00:03] PATIENT: Cough and fever.\n"
        "[00:06] PATIENT: No cough.\n"
        "[00:09] PATIENT: No fever."
    )
    note = offline_rules(text)
    affected = note["history_of_presenting_illness"] + note["review_of_systems"]
    assert len({e["conflict"]["id"] for e in affected}) == 1
