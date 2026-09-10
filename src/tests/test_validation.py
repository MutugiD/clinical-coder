from copy import deepcopy
from pathlib import Path

import pytest

from clinical_scribe.contracts import empty_note
from clinical_scribe.errors import StageError
from clinical_scribe.extraction import offline_rules
from clinical_scribe.validation import validate

FIXTURES = Path(__file__).parent / "fixtures"


def test_alternate_transcript_roles_and_certainty():
    text = (FIXTURES / "alternate_consultation.txt").read_text()
    note = offline_rules(text)
    assert validate(text, note) == {"valid": True}
    assert note["past_medical_history"] == "NOT_STATED"
    assert note["vitals"][0]["attribution"] == "nurse"
    assert all(
        e["attribution"] != "companion" for v in note.values() if isinstance(v, list) for e in v
    )
    assert note["assessment"][0]["kind"] == "considered_and_rejected"
    assert note["assessment"][-1]["certainty"] == "probable"


@pytest.mark.parametrize(
    "source,value",
    [
        ("Temperature is 36.8.", "Temperature is 38.6."),
        ("BP is 128 over 82.", "BP is 82/128."),
        ("Start medicine 20 milligrams for four weeks.", "Start medicine 40 mg for four weeks."),
        ("Start medicine 20 milligrams for four weeks.", "Start medicine 20 mg for two weeks."),
        ("Start medicine 20 milligrams for four weeks.", "Start medicine 20 ml for four weeks."),
        ("Start medicine 20 milligrams for four weeks.", "Start medicine 4 mg for 20 weeks."),
        ("Temperature is -1.", "Temperature is 1."),
    ],
)
def test_changed_numbers_and_units_rejected(source, value):
    text = "[00:00] DOCTOR: " + source
    note = offline_rules(text)
    section = "vitals" if note["vitals"] != "NOT_STATED" else "plan"
    note[section][0]["value"] = value
    with pytest.raises(StageError, match="changes source"):
        validate(text, note)


@pytest.mark.parametrize(
    "source,value",
    [
        ("BP is 128 over 82.", "BP is 128/82."),
        ("Start medicine 20 milligrams for four weeks.", "Start medicine twenty mg for 4 weeks."),
        ("Start medicine 20 mg for 4 weeks.", "Start medicine twenty milligrams for four weeks."),
        (
            "Start medicine moja tablet mara mbili kwa siku.",
            "Start medicine 1 tablet mara 2 kwa siku.",
        ),
        ("Start medicine twenty-one mg.", "Start medicine 21 milligrams."),
    ],
)
def test_permitted_normalizations_both_directions(source, value):
    text = "[00:00] DOCTOR: " + source
    note = offline_rules(text)
    section = "vitals" if note["vitals"] != "NOT_STATED" else "plan"
    note[section][0]["value"] = value
    assert validate(text, note)["valid"]


def test_context_cannot_supply_numbers():
    text = "[00:00] DOCTOR: Have you had cough for 5 days?\n[00:03] PATIENT: No cough."
    note = offline_rules(text)
    entry = note["review_of_systems"][0]
    assert "5" in entry["context_span"]["text"]
    entry["value"] = "No cough for 5 days."
    with pytest.raises(StageError):
        validate(text, note)


@pytest.mark.parametrize("code", ["K29.7", "M01AB05", "LAB-EC-0412", "ALG-EC-0003", "PGP-EC-0330"])
def test_codes_rejected_anywhere_in_note(code):
    text = "[00:00] NURSE: Pulse 70."
    note = offline_rules(text)
    note["vitals"][0]["extra"] = {code: "injected"}
    with pytest.raises(StageError, match="code-like"):
        validate(text, note)


def test_family_history_cannot_be_moved_to_assessment():
    text = "[00:00] DOCTOR: Any family history?\n[00:03] PATIENT: My father had ulcers."
    note = offline_rules(text)
    entry = note["family_history"].pop()
    entry["certainty"] = "confirmed"
    note["family_history"] = "NOT_STATED"
    note["assessment"] = [entry]
    with pytest.raises(StageError, match="section assessment"):
        validate(text, note)


def test_thinking_aloud_marker_cannot_be_removed():
    text = "[00:00] DOCTOR: I was wondering whether an ulcer, but no."
    note = offline_rules(text)
    del note["assessment"][0]["kind"]
    with pytest.raises(StageError, match="thinking-aloud"):
        validate(text, note)


def test_companion_requires_attribution():
    text = "[00:00] COMPANION: She has a cough."
    note = empty_note()
    entry = {
        "value": "She has a cough.",
        "span": {"ref": "[00:00]", "text": "She has a cough."},
        "confidence": 1.0,
        "attribution": "companion",
    }
    note["history_of_presenting_illness"] = [entry]
    assert validate(text, note)["valid"]
    del entry["attribution"]
    with pytest.raises(StageError):
        validate(text, note)


def test_negation_cannot_be_removed_from_value_or_span():
    text = "[00:00] DOCTOR: Any vomiting?\n[00:03] PATIENT: No vomiting."
    note = offline_rules(text)
    entry = note["review_of_systems"][0]
    entry["value"] = "vomiting."
    entry["span"]["text"] = "vomiting."
    with pytest.raises(StageError, match="truncates"):
        validate(text, note)


def test_conflicts_preserve_both_statements_and_cannot_be_hidden():
    text = (FIXTURES / "conflicting_consultation.txt").read_text()
    original = offline_rules(text)
    assert validate(text, original)["valid"]
    assert (
        original["chief_complaint"][0]["conflict"]["id"]
        == original["review_of_systems"][0]["conflict"]["id"]
    )
    assert (
        original["medication_history"][0]["conflict"]
        == original["medication_history"][1]["conflict"]
    )
    note = deepcopy(original)
    del note["review_of_systems"][0]["conflict"]
    with pytest.raises(StageError, match="conflict"):
        validate(text, note)
    note = deepcopy(original)
    note["review_of_systems"] = note["review_of_systems"][1:]
    with pytest.raises(StageError, match="omitted"):
        validate(text, note)


def test_uncertainty_and_context_tampering():
    text = (FIXTURES / "alternate_consultation.txt").read_text()
    note = offline_rules(text)
    note["assessment"][-1]["certainty"] = "confirmed"
    with pytest.raises(StageError, match="certainty"):
        validate(text, note)
    note = offline_rules(text)
    note["allergies"][0]["context_span"]["text"] = "invented question"
    with pytest.raises(StageError, match="context span"):
        validate(text, note)
