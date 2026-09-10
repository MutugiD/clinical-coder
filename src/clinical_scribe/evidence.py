"""Conservative conversational scope and verbatim evidence segmentation."""

import re
from dataclasses import dataclass

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
    r"may be|possible|i think|suspect\w*|consistent with|impression|confirmed)\b",
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


def sections_for(turn: Turn, text: str, topic: str | None) -> tuple[str, ...]:
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
            return ("assessment",)
        return ()
    if FAMILY.search(text):
        return ("family_history",)
    if topic == "chief_complaint":
        return ("chief_complaint", "history_of_presenting_illness")
    if topic == "review_of_systems":
        return (
            ("review_of_systems",) if NEGATIVE.search(text) else ("history_of_presenting_illness",)
        )
    if topic:
        return (topic,)
    if SYMPTOMS.search(text):
        return ("history_of_presenting_illness",)
    return ()


def evidence(transcript: str, stage: str = "extract") -> list[Evidence]:
    result = []
    context = None
    topic = None
    for turn in parse_transcript(transcript, stage):
        for text in pieces(turn.text):
            if turn.speaker == "DOCTOR" and "?" in text:
                new_topic = question_topic(text, topic)
                topic = new_topic
                context = turn
            result.append(
                Evidence(
                    len(result),
                    turn,
                    text,
                    sections_for(turn, text, topic),
                    context if turn.speaker == "PATIENT" else None,
                    bool(REJECTED.search(text)),
                )
            )
    return result
