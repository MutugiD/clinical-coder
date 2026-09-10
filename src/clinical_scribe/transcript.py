"""Parse speaker turns without altering their evidence text."""

import re
from dataclasses import dataclass

from clinical_scribe.errors import StageError

TURN = re.compile(r"^(\[(\d{2,}):(\d{2})\]) (DOCTOR|PATIENT|COMPANION|NURSE): (.+)$")


@dataclass(frozen=True)
class Turn:
    ref: str
    speaker: str
    text: str
    line: int


def parse_transcript(text: str, stage: str = "extract") -> list[Turn]:
    turns = []
    seen = set()
    previous = -1
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        match = TURN.fullmatch(line)
        if not match or not match[5].strip() or int(match[3]) > 59:
            raise StageError(stage, f"line {number}: invalid timestamp, speaker, or empty text")
        seconds = 60 * int(match[2]) + int(match[3])
        if match[1] in seen or seconds < previous:
            raise StageError(stage, f"line {number}: duplicate or decreasing timestamp")
        seen.add(match[1])
        previous = seconds
        turns.append(Turn(match[1], match[4], match[5], number))
    if not turns:
        raise StageError(stage, "empty transcript")
    return turns
