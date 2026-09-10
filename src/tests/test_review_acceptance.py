import subprocess
import sys
from pathlib import Path
from shutil import copytree

import pytest

from clinical_scribe.errors import StageError
from clinical_scribe.extraction import offline_rules
from clinical_scribe.resolver import resolve
from clinical_scribe.validation import validate


@pytest.mark.parametrize("negative", ["I do not take", "I don't take", "I don’t take"])
def test_medication_contradiction_marks_both_and_neither_codes(negative):
    text = (
        "[00:00] DOCTOR: Are you taking any medicines?\n"
        "[00:04] PATIENT: I take diclofenac every day.\n"
        f"[00:08] PATIENT: {negative} diclofenac."
    )
    note = offline_rules(text)
    first, second = note["medication_history"]
    assert first["conflict"] == second["conflict"]
    assert first["span"] != second["span"]
    resolved = resolve(note, "kind,code,name,synonyms\ndrug,M01AB05,Diclofenac,voltaren\n")
    assert all(e["code"] is None for e in resolved["medication_history"])


def test_leading_decimal_dose_contradiction_is_preserved():
    text = (
        "[00:00] DOCTOR: Any medicines?\n"
        "[00:04] PATIENT: Examplez .5 mg daily.\n"
        "[00:08] PATIENT: Examplez .6 mg daily."
    )
    first, second = offline_rules(text)["medication_history"]
    assert first["conflict"] == second["conflict"]


def test_familiar_timestamps_do_not_supply_familiar_facts():
    text = "[00:00] DOCTOR: Any surgeries before?\n[00:04] PATIENT: Appendix, 2022."
    note = offline_rules(text)
    assert note["past_surgical_history"][0]["value"] == "Appendix, 2022."
    assert validate(text, note)["valid"]
    note["past_surgical_history"][0]["value"] = "Appendix, 2019."
    with pytest.raises(StageError):
        validate(text, note)


def test_changed_reference_cannot_reuse_real_quote():
    text = "[00:00] NURSE: Pulse 80.\n[00:04] NURSE: Temperature 37.2."
    note = offline_rules(text)
    note["vitals"][0]["span"]["ref"] = "[00:04]"
    with pytest.raises(StageError, match="verbatim"):
        validate(text, note)


def test_future_warning_is_not_current_symptom_or_diagnosis():
    text = "[00:00] DOCTOR: Return sooner if you vomit blood."
    note = offline_rules(text)
    assert note["assessment"] == note["review_of_systems"] == "NOT_STATED"
    assert note["plan"][0]["value"] == "Return sooner if you vomit blood."


def test_unknown_medication_stays_present_and_uncoded():
    text = "[00:00] DOCTOR: Any medicines?\n[00:04] PATIENT: Examplez every day."
    note = offline_rules(text)
    resolved = resolve(note, "kind,code,name,synonyms\ndrug,N02BE01,Paracetamol,panadol\n")
    assert resolved["medication_history"][0]["value"] == "Examplez every day."
    assert resolved["medication_history"][0]["code"] is None


def test_knowledge_runs_where_no_note_or_outputs_exist(tmp_path):
    copytree("schemas", tmp_path / "schemas")
    source = tmp_path / "guideline.txt"
    source.write_text((Path(__file__).parent / "fixtures" / "alternate_guideline.txt").read_text())
    result = subprocess.run(
        [
            sys.executable,
            str(Path("scribe").resolve()),
            "knowledge",
            "--source",
            str(source),
            "--out",
            str(tmp_path / "knowledge.json"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "outputs").exists()
