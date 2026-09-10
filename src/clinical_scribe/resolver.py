"""Deterministic, register-only lookup with conservative abstention."""

import re
import unicodedata
from copy import deepcopy
from difflib import SequenceMatcher

from clinical_scribe.contracts import enforce
from clinical_scribe.evidence import FAMILY, NEGATION, REJECTED
from clinical_scribe.loaders import RegisterEntry, parse_register
from clinical_scribe.validation import reject_codes

MATCH_VERSION = "register-match-v1"
KINDS = {
    "assessment": {"diagnosis"},
    "past_medical_history": {"diagnosis"},
    "chief_complaint": {"diagnosis"},
    "history_of_presenting_illness": {"diagnosis"},
    "past_surgical_history": {"procedure"},
    "medication_history": {"drug"},
    "allergies": {"allergen"},
    "plan": {"drug", "lab", "procedure"},
}
SYSTEMS = {"diagnosis": "ICD-10", "drug": "ATC", "lab": "EC", "procedure": "EC", "allergen": "EC"}
NEGATED = re.compile(NEGATION.pattern + r"|\bwithout\b", re.I)
CONDITIONAL = re.compile(r"\b(if|unless|endapo|ikiwa)\b", re.I)


def tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold()))


def contains(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    return bool(needle) and any(
        haystack[i : i + len(needle)] == needle for i in range(len(haystack) - len(needle) + 1)
    )


def aliases(entry: RegisterEntry, section: str) -> list[tuple[str, ...]]:
    names = [tokens(name) for name in (entry.name, *entry.synonyms)]
    # Contextual vocabulary expansion selects an existing procedure, never a code literal.
    if section == "past_surgical_history" and any(
        name in {("appendicectomy",), ("appendectomy",), ("appendix", "removal")} for name in names
    ):
        names.append(("appendix",))
    return [name for name in names if name]


def score(value: tuple[str, ...], names: list[tuple[str, ...]]) -> float:
    if any(contains(value, name) for name in names):
        return 1.0
    best = 0.0
    for name in names:
        phrase = " ".join(name)
        if len(phrase) < 5:
            continue
        for i in range(len(value) - len(name) + 1):
            window = " ".join(value[i : i + len(name)])
            best = max(best, SequenceMatcher(None, phrase, window, autojunk=False).ratio())
    # Rounding must never promote a near match into the exact-match sentinel.
    return min(round(best, 4), 0.9999) if best >= 0.8 else 0.0


def resolve_element(section: str, element: dict, register: list[RegisterEntry]) -> dict:
    result = deepcopy(element)
    result.update(
        extraction_confidence=element["confidence"],
        confidence=0.0,
        code=None,
        code_system="",
        alternatives=[],
        status="unresolved",
        resolver_version=MATCH_VERSION,
    )
    value = element["value"]
    if (
        element.get("conflict")
        or element.get("kind") == "considered_and_rejected"
        or element.get("attribution") == "companion"
        or FAMILY.search(value)
        or REJECTED.search(value)
        or NEGATED.search(value)
        or CONDITIONAL.search(value)
    ):
        result["resolution_reason"] = "excluded by attribution, conflict, rejection or polarity"
        return result
    permitted = KINDS.get(section, set())
    candidates = [
        (score(tokens(value), aliases(entry, section)), entry)
        for entry in register
        if entry.kind in permitted
    ]
    candidates = sorted((c for c in candidates if c[0]), key=lambda c: (-c[0], c[1].code))
    exact = [entry for value_score, entry in candidates if value_score == 1.0]
    if len(exact) == 1:
        selected = exact[0]
        result.update(
            code=selected.code,
            code_system=SYSTEMS[selected.kind],
            confidence=1.0,
            status="resolved",
            resolution_reason="unique exact alias",
        )
    elif len(exact) > 1:
        result.update(status="ambiguous", resolution_reason="multiple exact register matches")
    else:
        result["resolution_reason"] = "no exact register match"
    result["alternatives"] = [
        {"code": entry.code, "name": entry.name, "score": value_score}
        for value_score, entry in candidates
        if entry.code != result["code"]
    ][:5]
    return result


def resolve(note: dict, register_text: str, source: str = "register") -> dict:
    # Parse first so every corrupt register fails, even for an otherwise empty note.
    register = parse_register(register_text, source)
    enforce("resolve_request", {"note": note, "register": register_text}, "resolve")
    reject_codes(note, "resolve")
    result = {
        section: "NOT_STATED"
        if entries == "NOT_STATED"
        else [resolve_element(section, entry, register) for entry in entries]
        for section, entries in note.items()
    }
    enforce("resolve_response", result, "resolve")
    return result
