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
    period = time[0] if time else "current"
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
    return result


def conflict_groups(items: list[Evidence]) -> dict[int, dict[str, str]]:
    by_concept: dict[str, list] = defaultdict(list)
    for item in items:
        for concept, negative, numbers in claims(item):
            by_concept[concept].append((item, negative, numbers))
    result = {}
    for concept, entries in by_concept.items():
        affected = set()
        for i, (left, neg_left, nums_left) in enumerate(entries):
            for right, neg_right, nums_right in entries[i + 1 :]:
                if left.turn.ref == right.turn.ref:
                    continue
                if neg_left != neg_right or (nums_left and nums_right and nums_left != nums_right):
                    affected.update((left.index, right.index))
        if affected:
            identity = concept + ":" + ",".join(map(str, sorted(affected)))
            group = {
                "id": "conflict-" + hashlib.sha256(identity.encode()).hexdigest()[:12],
                "reason": "Inconsistent patient statements; clinician review required",
            }
            for index in affected:
                result[index] = group
    return result
