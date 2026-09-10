from copy import deepcopy

import pytest

from clinical_scribe.contracts import empty_note, enforce
from clinical_scribe.errors import StageError


def element():
    return {
        "value": "Appendix, 2020.",
        "span": {"ref": "[00:05]", "text": "Appendix, 2020."},
        "context_span": {"ref": "[00:02]", "text": "Any past surgery?"},
        "confidence": 0.9,
        "conflict": {"id": "history-a", "reason": "Different dates reported"},
    }


def test_optional_metadata_preserves_minimum_note_contract():
    note = empty_note()
    note["past_surgical_history"] = [element()]
    enforce("note", note, "validate")
    del note["past_surgical_history"][0]["context_span"]
    del note["past_surgical_history"][0]["conflict"]
    enforce("note", note, "validate")


@pytest.mark.parametrize(
    "field,bad",
    [
        ("context_span", {"ref": "00:02", "text": "Any past surgery?"}),
        ("context_span", {"ref": "[00:02]"}),
        ("context_span", {"ref": "[00:02]", "text": ""}),
        ("conflict", {"id": "history-a"}),
        ("conflict", {"id": "", "reason": "Different dates"}),
        ("conflict", True),
    ],
)
def test_invalid_optional_metadata_rejected(field, bad):
    note = empty_note()
    entry = element()
    entry[field] = bad
    note["past_surgical_history"] = [entry]
    with pytest.raises(StageError, match="schema violation"):
        enforce("note", note, "validate")


def test_context_does_not_replace_required_primary_span():
    entry = element()
    del entry["span"]
    note = empty_note()
    note["past_surgical_history"] = [entry]
    with pytest.raises(StageError, match="schema violation"):
        enforce("note", note, "validate")


@pytest.mark.parametrize("certainty", ["confirmed", "probable", "differential"])
def test_resolved_schema_preserves_certainty_and_context(certainty):
    entry = deepcopy(element())
    entry.update(
        certainty=certainty, code=None, code_system="", alternatives=[], status="unresolved"
    )
    note = empty_note()
    note["assessment"] = [entry]
    enforce("resolved", note, "resolve")
