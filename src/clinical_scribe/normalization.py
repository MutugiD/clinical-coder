"""Small, reversible numeric and unit equivalences; no free translation."""

import re

WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "moja": 1,
    "mbili": 2,
    "tatu": 3,
    "nne": 4,
    "tano": 5,
    "sita": 6,
    "saba": 7,
    "nane": 8,
    "tisa": 9,
    "kumi": 10,
    "ishirini": 20,
    "thelathini": 30,
    "arobaini": 40,
    "hamsini": 50,
    "sitini": 60,
    "sabini": 70,
    "themanini": 80,
    "tisini": 90,
}
EN_ONES = "one|two|three|four|five|six|seven|eight|nine"
EN_TENS = "twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
SW_ONES = "moja|mbili|tatu|nne|tano|sita|saba|nane|tisa"
SW_TENS = "kumi|ishirini|thelathini|arobaini|hamsini|sitini|sabini|themanini|tisini"


def normalize(text: str) -> tuple[str, ...]:
    text = text.casefold().replace("’", "'")
    for tens, ones, join in ((EN_TENS, EN_ONES, r"[ -]+"), (SW_TENS, SW_ONES, r"\s+na\s+")):
        text = re.sub(
            rf"\b({tens}){join}({ones})\b", lambda m: str(WORDS[m[1]] + WORDS[m[2]]), text
        )
    text = re.sub(r"\b(" + "|".join(WORDS) + r")\b", lambda m: str(WORDS[m[0]]), text)
    text = re.sub(
        r"\b([1-9]) hundred(?: and)?(?: (\d{1,2}))?\b",
        lambda m: str(int(m[1]) * 100 + int(m[2] or 0)),
        text,
    )
    text = re.sub(r"(?<=\d)\s+over\s+(?=\d)", "/", text)
    for pattern, replacement in (
        (r"\bmilligrams?\b", "mg"),
        (r"\bmillilitres?\b|\bmilliliters?\b", "ml"),
        (r"\bkilograms?\b", "kg"),
        (r"\bdegrees? celsius\b", "celsius"),
    ):
        text = re.sub(pattern, replacement, text)
    # Decimal points, signs, and numerical order are retained, unlike bag-of-digit checks.
    return tuple(re.findall(r"-?(?:\d+(?:\.\d+)?|\.\d+)|[^\W\d_]+(?:'[^\W\d_]+)?|[/+%<>=]", text))
