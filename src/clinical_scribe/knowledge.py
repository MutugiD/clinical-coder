"""Source-only guideline rules, exact citations and bounded review prompts."""

import re
from dataclasses import dataclass

from clinical_scribe.contracts import enforce
from clinical_scribe.errors import StageError
from clinical_scribe.normalization import normalize

RULE_VERSION = "guideline-rules-v1"
HEADER = re.compile(
    r"^SOURCE:\s*(?P<source>[^\n]+?),\s*[^,\n]+edition,\s*"
    r"Section\s+(?P<section>\d+(?:\.\d+)*),\s*page\s+(?P<page>[1-9]\d*)\.",
    re.I,
)
CLASS = re.compile(
    r"\b(NSAIDs?|PPIs?|proton pump inhibitor|non-steroidal anti-inflammatory)\b", re.I
)


@dataclass(frozen=True)
class Excerpt:
    source: str
    section: str
    page: int
    condition: str
    heading: str
    sentences: tuple[str, ...]

    def row(self, kind: str, fields: dict, quote: str) -> dict:
        return {
            "type": kind,
            "fields": fields,
            "source": self.source,
            "section": self.section,
            "page": self.page,
            "quote": quote,
        }


def parse_excerpt(source: str) -> Excerpt:
    text = source.strip()
    header = HEADER.match(text)
    if not header:
        raise StageError("knowledge", "missing or unsupported SOURCE citation header")
    body = text[header.end() :].strip()
    heading = re.match(r"(?P<section>\d+(?:\.\d+)*)\s+(?P<title>[^.\n]+)\.", body)
    if not heading or heading["section"] != header["section"]:
        raise StageError("knowledge", "section heading does not match citation metadata")
    body = body[heading.end() :].strip()
    if re.search(r"(?m)^\s*(?:SOURCE:|\d+(?:\.\d+)+\s+)", body):
        raise StageError("knowledge", "multiple citation blocks are not supported")
    sentences = tuple(
        part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z])", body) if part.strip()
    )
    if not sentences:
        raise StageError("knowledge", "citation block contains no recommendations")
    return Excerpt(
        header["source"],
        header["section"],
        int(header["page"]),
        heading["title"],
        heading[0],
        sentences,
    )


def derive_rows(excerpt: Excerpt) -> list[dict]:
    rows = []
    for sentence in excerpt.sentences:
        alarm = re.fullmatch(
            r"Alarm features requiring (?P<action>urgent referral):\s*(?P<features>.+)\.",
            sentence,
            re.I,
        )
        test = re.fullmatch(
            r"Test for (?P<target>.+?) using a (?P<test>.+?);\s*"
            r"(?P<constraint>the patient should not have taken a (?P<exposure>.+?) "
            r"in the preceding (?P<interval>.+?)) as (?P<reason>.+)\.",
            sentence,
            re.I,
        )
        conditional = re.fullmatch(
            r"(?P<condition>Patients .+?) should (?P<action>.+)\.", sentence, re.I
        )
        treatment = re.fullmatch(
            r"(?P<treatment>A .+?) at (?P<dose>.+?) for (?P<duration>.+?) is recommended\.",
            sentence,
            re.I,
        )
        if alarm:
            features = [feature.strip() for feature in alarm["features"].split(",")]
            if any(not feature for feature in features):
                raise StageError("knowledge", "empty alarm feature in source")
            for feature in features:
                rows.append(
                    excerpt.row(
                        "red_flag",
                        {
                            "condition": excerpt.condition,
                            "feature": feature,
                            "action": alarm["action"],
                            "severity": "urgent",
                        },
                        sentence,
                    )
                )
        elif test:
            rows.append(
                excerpt.row(
                    "test_constraint",
                    {
                        "target": test["target"],
                        "test": test["test"],
                        "constraint": test["constraint"],
                        "exposure": test["exposure"],
                        "lookback_interval": test["interval"],
                        "reason": test["reason"],
                    },
                    sentence,
                )
            )
        elif conditional and CLASS.search(sentence):
            rows.append(
                excerpt.row(
                    "drug_class_rule",
                    {
                        "condition_or_exposure": conditional["condition"],
                        "action": conditional["action"],
                        "severity": "recommendation",
                    },
                    sentence,
                )
            )
        elif treatment and CLASS.search(sentence):
            rows.append(
                excerpt.row(
                    "drug_class_rule",
                    {
                        "condition_or_exposure": excerpt.condition,
                        "treatment": treatment["treatment"],
                        "dose": treatment["dose"],
                        "duration": treatment["duration"],
                        "action": sentence,
                        "severity": "recommendation",
                    },
                    sentence,
                )
            )
        else:
            # The parser is bounded: an unfamiliar sentence cannot quietly disappear.
            raise StageError("knowledge", "unsupported guideline sentence", sentence)
    return rows


def corpus_gaps(rows: list[dict]) -> list[str]:
    gaps = []
    doses = [
        normalize(row["fields"].get("dose", ""))
        for row in rows
        if row["type"] == "drug_class_rule"
        and re.search(r"\b(PPI|proton pump inhibitor)\b", row["fields"].get("treatment", ""), re.I)
    ]
    if not any(
        unit == "mg" and i > 0 and re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", dose[i - 1])
        for dose in doses
        for i, unit in enumerate(dose)
    ):
        gaps.append("The excerpt does not specify a PPI dose in milligrams.")
    # Supported rules have no age-specific treatment branch; alarm age is not a dose rule.
    treatments = [str(row["fields"]) for row in rows if row["type"] == "drug_class_rule"]
    if not any(
        re.search(r"\b(paediatric|pediatric|children|child|under 18)\b", text, re.I)
        for text in treatments
    ):
        gaps.append("The excerpt does not specify treatment for patients under 18.")
    return gaps


def review_prose(rows: list[dict], gaps: list[str], note: dict | None) -> str:
    kinds = {row["type"] for row in rows}
    parts = []
    if "drug_class_rule" in kinds:
        parts.append(
            "Confirm the medicine's class before applying the cited exposure and treatment rules; "
            "review whether their conditions hold."
        )
    if "test_constraint" in kinds:
        plan = note.get("plan", "NOT_STATED") if note else "NOT_STATED"
        if isinstance(plan, list) and any(
            "stool antigen" in entry["value"].casefold() for entry in plan
        ):
            constraint = next(row for row in rows if row["type"] == "test_constraint")
            parts.append(
                "The plan mentions a stool-antigen test. Ask about prior exposure to the cited "
                "medicine class and clarify planned treatment/test timing: the cited constraint "
                f"requires no {constraint['fields']['exposure']} in the preceding "
                f"{constraint['fields']['lookback_interval']}."
            )
            if any("PPI dose in milligrams" in gap for gap in gaps) and any(
                re.search(r"\bstart\b", entry["value"], re.I) for entry in plan
            ):
                parts.append(
                    "The prescription is the doctor's stated plan; the excerpt does not "
                    "independently validate its milligram dose. Do not invent a test date."
                )
        else:
            parts.append(
                "If ordering the cited test, check prior exposure and the specified lookback "
                "interval before scheduling it."
            )
    if "red_flag" in kinds:
        parts.append(
            "Assess the listed alarm features and confirm age where relevant; an undocumented "
            "finding is not a negative response."
        )
    if gaps:
        parts.append(
            "Ask the clinician to resolve the listed corpus gaps; the excerpt cannot supply "
            "missing dose or age-specific guidance."
        )
    parts.append(
        "Do not infer drug-class membership, invent patient facts, upgrade diagnostic certainty, "
        "or change prescriptions and orders automatically."
    )
    return " ".join(parts)


def verify_knowledge(source: str, result: dict) -> None:
    enforce("knowledge_response", result, "knowledge")
    excerpt = parse_excerpt(source)
    for index, row in enumerate(result["rows"]):
        if row["quote"] not in source:
            raise StageError("knowledge", f"row {index}: quotation is not verbatim in source")
        if (row["source"], row["section"], row["page"]) != (
            excerpt.source,
            excerpt.section,
            excerpt.page,
        ):
            raise StageError("knowledge", f"row {index}: citation metadata differs from source")
    expected = derive_rows(excerpt)
    if result["rows"] != expected:
        raise StageError(
            "knowledge", "rule fields, ordering or completeness differ from source rules"
        )
    if result["not_in_corpus"] != corpus_gaps(expected):
        raise StageError("knowledge", "corpus gaps differ from source-only evaluation")
    if len(result["prose"].split()) >= 200:
        raise StageError("knowledge", "prose must be under 200 words")


def knowledge(source: str, note: dict | None = None) -> dict:
    request = {"source": source}
    if note is not None:
        request["note"] = note
    enforce("knowledge_request", request, "knowledge")
    rows = derive_rows(parse_excerpt(source))
    gaps = corpus_gaps(rows)
    result = {"rows": rows, "not_in_corpus": gaps, "prose": review_prose(rows, gaps, note)}
    verify_knowledge(source, result)
    return result
