"""Conservative conflicts between explicit patient assertions."""

import hashlib
import re
from collections import defaultdict

from clinical_scribe.evidence import NEGATIVE, Evidence
from clinical_scribe.normalization import normalize

SYMPTOM_ROOTS = {
    "vomiting": r"vomit\w*|kutapika",
    "cough": r"cough\w*|kikohozi",
    "fever": r"fever|homa",
    "smoking": r"smok\w*",
    "diarrhoea": r"diarrh\w*",
    "weight_loss": r"weight loss",
}


def claims(item: Evidence) -> list[tuple[str, bool, tuple[str, ...]]]:
    if item.turn.speaker != "PATIENT" or not item.sections or item.rejected:
        return []
    if set(item.sections) & {"family_history", "past_medical_history", "past_surgical_history"}:
        return []
    text = item.text.casefold().replace("\u2019", "'")
    time = re.search(r"\b(yesterday|last year|previously|today|now|zamani)\b", text)
    period = time[0] if time and time[0] not in {"today", "now"} else "current"
    numbers = tuple(t for t in normalize(text) if re.fullmatch(r"-?(?:\d+(?:\.\d+)?|\.\d+)", t))
    negative = bool(NEGATIVE.search(text))
    result = []
    for concept, pattern in SYMPTOM_ROOTS.items():
        if re.search(r"\b(?:" + pattern + r")\b", text):
            result.append((concept + ":" + period, negative, numbers))
    if "medication_history" in item.sections:
        name = re.match(
            r"(?:i (?:(?:do not|don't|never) )?(?:take|use|am (?:not )?taking)\s+)?"
            r"([a-z][a-z-]+)",
            text,
        )
        if name and name[1] not in {"one", "two", "no", "none", "sometimes", "na"}:
            result.append(("medication:" + name[1] + ":" + period, negative, numbers))
    if "allergies" in item.sections:
        if re.fullmatch(r"(?:no (?:known )?allergies|i have no (?:known )?allergies)[.!]?", text):
            result.append(("allergy:*:" + period, True, ()))
        name = re.match(
            r"(?:(?:i have|i am|i'm)\s+)?(?:(?:no|not|an?)\s+)?"
            r"(?:allerg(?:y|ic)\s+to\s+)?([a-z][a-z-]+)",
            text,
        )
        if name and name[1] not in {"rash", "nilipata", "none", "known", "allergies"}:
            result.append(("allergy:" + name[1] + ":" + period, negative, ()))
    return result


def conflict_groups(items: list[Evidence]) -> dict[int, dict[str, str]]:
    by_concept: dict[str, list] = defaultdict(list)
    for item in items:
        for concept, negative, numbers in claims(item):
            by_concept[concept].append((item, negative, numbers))
    for concept, entries in list(by_concept.items()):
        if concept.startswith("allergy:") and not concept.startswith("allergy:*:"):
            period = concept.rsplit(":", 1)[1]
            entries.extend(by_concept.get("allergy:*:" + period, []))
    components: list[tuple[set[int], set[str]]] = []
    for concept, entries in by_concept.items():
        affected = set()
        for i, (left, neg_left, nums_left) in enumerate(entries):
            for right, neg_right, nums_right in entries[i + 1 :]:
                if neg_left != neg_right or (nums_left and nums_right and nums_left != nums_right):
                    affected.update((left.index, right.index))
        if affected:
            concepts = {concept}
            separate = []
            for indices, names in components:
                if indices & affected:
                    affected.update(indices)
                    concepts.update(names)
                else:
                    separate.append((indices, names))
            components = [*separate, (affected, concepts)]
    result = {}
    for affected, concepts in components:
        identity = ",".join(sorted(concepts)) + ":" + ",".join(map(str, sorted(affected)))
        group = {
            "id": "conflict-" + hashlib.sha256(identity.encode()).hexdigest()[:12],
            "reason": "Inconsistent patient statements; clinician review required",
        }
        for index in affected:
            result[index] = group
    return result
