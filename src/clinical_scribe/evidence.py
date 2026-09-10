"""Conservative conversational scope and verbatim evidence segmentation."""

import re
from dataclasses import dataclass, replace

from clinical_scribe.errors import StageError
from clinical_scribe.transcript import Turn, parse_transcript

FAMILY = re.compile(
    r"\b(my (?:father|mother|brother|sister|parent|grand\w+)|family|familia|baba|mama)\b", re.I
)
REJECTED = re.compile(
    r"\b(but no|let['’]?s not|not go there|ruled out|considered and rejected|"
    r"not pursue|no longer considering|discard(?:ed)?)\b",
    re.I,
)
NEGATION = re.compile(
    r"\b(no|not|never|den(?:y|ies|ied)|sina|hakuna|hamna|"
    r"(?:don|doesn|didn|isn|aren|wasn|weren|hasn|haven|hadn|can|couldn|wouldn|shouldn)['’]t)\b",
    re.I,
)
NEGATIVE = re.compile(NEGATION.pattern + r"|\b(normal|sawa)\b", re.I)
VITAL = re.compile(
    r"\b(bp|blood pressure|pulse|temperature|heart rate|respiratory rate|spo2|oxygen saturation)\b",
    re.I,
)
EXAM = re.compile(
    r"\b(abdomen (?:is|soft)|tenderness|guarding|lungs? (?:are|clear)|"
    r"chest (?:is|clear)|heart sounds|on examination|exam:)\b",
    re.I,
)
ASSESSMENT = re.compile(
    r"\b(diagnos\w*|assessment|most likely|probably|probable|differential|could be|"
    r"may be|possible|i think|suspect\w*|consistent with|impression|confirmed|"
    r"you have|patient has|wondering whether)\b",
    re.I,
)
PLAN = re.compile(
    r"\b(we will|start|stop|check|test for|order|prescribe|continue|return|come back|"
    r"follow.up|refer|avoid|seek|review in|sooner if)\b",
    re.I,
)
ACK = re.compile(
    r"^(?:sawa[, .]*|asante(?: daktari)?[, .]*|thank(?:s| you)[, .]*|"
    r"okay[, .]*|ok[, .]*|yes[, .]*)+$",
    re.I,
)
SYMPTOMS = re.compile(
    r"\b(vomit\w*|stool|weight|fever|cough|breath\w*|chest|swallow\w*|bleed\w*|"
    r"headache|pain|nausea|diarrh\w*|dizziness|rash|homa|kikohozi|kutapika|maumivu)\b",
    re.I,
)


@dataclass(frozen=True)
class Evidence:
    index: int
    turn: Turn
    text: str
    sections: tuple[str, ...]
    context: Turn | None
    rejected: bool = False


SYMPTOM_CONCEPTS = {
    "vomiting": r"vomit\w*|kutapika",
    "cough": r"cough\w*|kikohozi",
    "fever": r"fever|homa",
    "stool": r"stool|melaena|melena",
    "weight": r"weight",
    "diarrhoea": r"diarrh\w*",
    "pain": r"pain|maumivu",
    "breathing": r"breath\w*",
    "swallowing": r"swallow\w*|dysphagia",
    "bleeding": r"bleed\w*",
    "headache": r"headache",
    "nausea": r"nausea",
    "dizziness": r"dizziness",
    "rash": r"rash",
}


def symptom_concepts(text: str) -> set[str]:
    return {
        name
        for name, pattern in SYMPTOM_CONCEPTS.items()
        if re.search(r"\b(?:" + pattern + r")\b", text, re.I)
    }


def scoped_pieces(text: str, turn: Turn, topic: str | None, stage: str) -> list[str]:
    """Split independent assertions only; never copy shared numeric qualifiers."""
    if turn.speaker != "PATIENT":
        return [text]
    if re.search(r"\b(actually|correction|i meant|rather than)\b", text, re.I):
        raise StageError(stage, "unsupported correction scope; clinician review required", turn.ref)
    contrast = re.split(r"\s+but\s+", text, flags=re.I)
    if len(contrast) > 1:
        if all(symptom_concepts(part) for part in contrast):
            return contrast
        raise StageError(stage, "unsupported contrast scope", turn.ref)
    if topic == "medication_history" and re.search(r"\s+and\s+", text, re.I):
        if NEGATION.search(text):
            raise StageError(stage, "unsupported shared medication negation", turn.ref)
        parts = re.split(r"\s+and\s+", text, flags=re.I)
        # Only bare additional medicine names are independent here. Shared doses,
        # frequency and temporal qualifiers require a richer representation.
        if all(re.fullmatch(r"[A-Za-z][A-Za-z-]*[.]?", p) for p in parts[1:]):
            return parts
        raise StageError(stage, "unsupported coordinated medication qualifiers", turn.ref)
    return [text]


def question_topic(text: str, previous: str | None = None) -> str | None:
    patterns = (
        (r"surger|operat|upasuaji", "past_surgical_history"),
        (r"family|familia|anyone.*(?:ulcer|condition)", "family_history"),
        (r"allerg|mzio", "allergies"),
        (r"medicin|medicat|taking any|dawa", "medication_history"),
        (r"smok|drink|tobacco|alcohol|pombe", "social_history"),
        (
            r"medical history|previous.*diagnos|chronic|other conditions|past illnesses",
            "past_medical_history",
        ),
        (r"what brings|what seems|how can i help|chief complaint|tatizo", "chief_complaint"),
    )
    for pattern, topic in patterns:
        if re.search(pattern, text, re.I):
            return topic
    if re.search(r"how (?:much|often|long)|what dose|which|when", text, re.I) and previous:
        return previous
    if SYMPTOMS.search(text) and re.search(r"\b(any|do you|have you|je)\b", text, re.I):
        return "review_of_systems"
    if re.search(r"worse|where|pain|symptom|when|how long", text, re.I):
        return "history_of_presenting_illness"
    return None


def pieces(text: str) -> list[str]:
    # Preserve decimals and abbreviations such as H. pylori; split plan actions.
    sentences = re.split(r"(?<=[.!?;])\s+(?=[A-Z])", text)
    return [
        part.strip()
        for sentence in sentences
        for part in re.split(
            r",\s+(?:and\s+)?(?=(?:start|stop|check|order|prescribe|refer|continue)\b)",
            sentence,
            flags=re.I,
        )
        if part.strip()
    ]


def certainty(text: str) -> str:
    if re.search(
        r"\b(possible|possibly|could|may|might|differential|rule out|wondering whether)\b",
        text,
        re.I,
    ):
        return "differential"
    if re.search(
        r"\b(probabl\w*|most likely|likely|i think|suspect\w*|consistent with)\b", text, re.I
    ):
        return "probable"
    return "confirmed"


def sections_for(
    turn: Turn, text: str, topic: str | None, asked: set[str] | None = None
) -> tuple[str, ...]:
    if "?" in text or ACK.fullmatch(text) or turn.speaker == "COMPANION":
        return ()
    if turn.speaker in ("DOCTOR", "NURSE"):
        if REJECTED.search(text):
            return ("assessment",) if turn.speaker == "DOCTOR" else ()
        if PLAN.search(text):
            return ("plan",) if turn.speaker == "DOCTOR" else ()
        if VITAL.search(text):
            return ("vitals",)
        if EXAM.search(text):
            return ("examination",)
        if turn.speaker == "DOCTOR" and ASSESSMENT.search(text) and not FAMILY.search(text):
            if re.search(r"\b(if|unless|ikiwa|endapo)\b", text, re.I):
                return ()
            return ("assessment",)
        if turn.speaker == "DOCTOR" and SYMPTOMS.search(text) and not FAMILY.search(text):
            return ("history_of_presenting_illness",)
        return ()
    if FAMILY.search(text):
        return ("family_history",)
    if topic == "chief_complaint":
        return ("chief_complaint", "history_of_presenting_illness")
    if topic == "review_of_systems":
        concepts = symptom_concepts(text)
        if NEGATIVE.search(text) and concepts and concepts <= (asked or set()):
            return ("review_of_systems",)
        return ("history_of_presenting_illness",)
    if topic:
        return (topic,)
    if SYMPTOMS.search(text):
        return ("history_of_presenting_illness",)
    return ()


def evidence(transcript: str, stage: str = "extract") -> list[Evidence]:
    result = []
    context = None
    topic = None
    asked: set[str] = set()
    for turn in parse_transcript(transcript, stage):
        for text in pieces(turn.text):
            if turn.speaker == "DOCTOR" and "?" in text:
                new_topic = question_topic(text, topic)
                topic = new_topic
                context = turn
                asked = symptom_concepts(text) if topic == "review_of_systems" else set()
            for part in scoped_pieces(text, turn, topic, stage):
                result.append(
                    Evidence(
                        len(result),
                        turn,
                        part,
                        sections_for(turn, part, topic, asked),
                        context if turn.speaker == "PATIENT" else None,
                        bool(REJECTED.search(part)),
                    )
                )
    # Link standalone retractions across sentence/adjacent doctor-turn boundaries.
    for index, item in enumerate(result):
        if item.turn.speaker != "DOCTOR" or not re.fullmatch(
            r"(?:but no|let['’]?s not go there(?: yet)?|ruled out)[.!]?", item.text, re.I
        ):
            continue
        if (
            index
            and result[index - 1].turn.speaker == "DOCTOR"
            and ("assessment" in result[index - 1].sections)
        ):
            result[index - 1] = replace(result[index - 1], rejected=True)
        else:
            raise StageError(
                stage, "rejection continuation has no unambiguous hypothesis", item.turn.ref
            )
    return result


def require_supported(items: list[Evidence]) -> None:
    """Do not report successful extraction after dropping an unclassified turn."""
    unknown = []
    for item in items:
        if item.sections or item.turn.speaker == "COMPANION" or ACK.fullmatch(item.text):
            continue
        if item.turn.speaker == "DOCTOR" and (
            "?" in item.text
            or re.fullmatch(
                r"(?:habari|karibu|hello|hi|welcome|good morning)[, .!]*"
                r"(?:(?:habari|karibu|hello|welcome)[, .!]*)*",
                item.text,
                re.I,
            )
        ):
            continue
        unknown.append(item.turn.ref)
    if unknown:
        raise StageError(
            "extract", "cannot safely classify clinical turns: " + ", ".join(sorted(set(unknown)))
        )
