import re
from dataclasses import dataclass

from dsc_backend.boxes import load_json_object
from dsc_backend.errors import PipelineError

CATEGORIES = (
    "phone",
    "email",
    "id_number",
    "account_number",
    "card_number",
    "address",
    "date_of_birth",
    "name",
)

SPANS_FORMAT = {
    "type": "json_schema",
    "name": "sensitive_spans",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["category", "text"],
                    "properties": {
                        "category": {"type": "string", "enum": list(CATEGORIES)},
                        "text": {"type": "string"},
                    },
                },
            }
        },
    },
}

_MAX_MODEL_SPANS = 50
_MAX_SPAN_CHARS = 200


@dataclass(frozen=True)
class Span:
    category: str
    text: str
    source: str  # "pattern" or "model"


# Card numbers: 13-19 digits, single spaces or dashes allowed, Luhn checked.
_CARD = re.compile(r"(?<![\w+])\d(?:[ -]?\d){12,18}(?!\w)")
_IBAN = re.compile(r"(?<!\w)[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?(?!\w)")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# Phone numbers: an optional + or (, then digits with up to two separators
# between them. The digit count is checked separately.
_PHONE = re.compile(r"(?<![\w+(])(?:\+|\()?\d(?:[ .()-]{0,2}\d){6,16}(?!\w)")
_DIGITS = re.compile(r"(?<!\w)\d{8,19}(?!\w)")
_DATE = (
    r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
    r"|\d{1,2} [A-Za-z]{3,9},? \d{4}"
    r"|[A-Za-z]{3,9} \d{1,2},? \d{4}"
)
_BIRTH = re.compile(rf"(?i)\b(?:dob|d\.o\.b\.?|date of birth)\b[\s:.-]*({_DATE})(?!\w)")
_SORT_CODE = re.compile(r"(?i)\bsort[\s-]*code\b[\s:.-]*(\d{2}-\d{2}-\d{2})(?!\w)")


def pattern_spans(text: str) -> list[Span]:
    """Find common sensitive values with fixed rules. Never calls a model."""
    found: list[tuple[int, int, str]] = []

    def keep(start: int, end: int, category: str) -> None:
        if any(start < other_end and other_start < end for other_start, other_end, _ in found):
            return
        found.append((start, end, category))

    for match in _BIRTH.finditer(text):
        keep(match.start(1), match.end(1), "date_of_birth")
    for match in _SORT_CODE.finditer(text):
        keep(match.start(1), match.end(1), "account_number")
    for match in _CARD.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            keep(match.start(), match.end(), "card_number")
    for match in _IBAN.finditer(text):
        keep(match.start(), match.end(), "account_number")
    for match in _EMAIL.finditer(text):
        keep(match.start(), match.end(), "email")
    for match in _PHONE.finditer(text):
        value = match.group()
        digits = sum(char.isdigit() for char in value)
        separated = value.startswith(("+", "(")) or not value.isdigit()
        if 9 <= digits <= 15 and separated:
            keep(match.start(), match.end(), "phone")
    for match in _DIGITS.finditer(text):
        keep(match.start(), match.end(), "account_number")

    found.sort()
    return [Span(category, text[start:end], "pattern") for start, end, category in found]


def model_spans(reply: str, transcript: str) -> list[Span]:
    """Read Muse's sensitive spans and keep only the ones that are really in the text.

    A span must use a known category and occur verbatim, on word boundaries,
    in the transcript. Anything else is dropped, so an invented value can
    never be shown or masked.
    """
    data = load_json_object(reply)
    items = data.get("items") if data is not None else None
    if not isinstance(items, list):
        raise PipelineError(502, "The model request failed")
    spans: list[Span] = []
    seen: set[str] = set()
    for item in items[:_MAX_MODEL_SPANS]:
        if not isinstance(item, dict):
            continue
        category, text = item.get("category"), item.get("text")
        if category not in CATEGORIES or not isinstance(text, str):
            continue
        if len(text.strip()) < 2 or len(text) > _MAX_SPAN_CHARS or text in seen:
            continue
        if not occurs(transcript, text):
            continue
        seen.add(text)
        spans.append(Span(category, text, "model"))
    return spans


def merge_spans(model: list[Span], patterns: list[Span]) -> list[Span]:
    """Model spans first. A pattern span is kept when no model span holds it."""
    merged = list(model)
    for span in patterns:
        if any(span.text in kept.text for kept in merged):
            continue
        merged.append(span)
    return merged


def surnames(spans: list[Span], text: str) -> list[Span]:
    """Add the last word of each multi-word name, where it appears on its own.

    Muse marks "Thomas Greene" but not the "Dear Mr Greene" further down.
    """
    known = {span.text for span in spans}
    if not known:
        return []
    # Look only where no span already covers the text.
    rest = _boundary(sorted(known, key=len, reverse=True)).sub(" ", text)
    extra: list[Span] = []
    for span in spans:
        words = span.text.split()
        if span.category != "name" or len(words) < 2:
            continue
        last = words[-1].strip(".,")
        if len(last) < 3 or last in known:
            continue
        if not occurs(rest, last):
            continue
        known.add(last)
        extra.append(Span("name", last, span.source))
    return extra


def occurs(text: str, value: str) -> bool:
    return _boundary([value]).search(text) is not None


def mask_text(text: str, spans: list[Span]) -> str:
    """Replace every occurrence of each span with [CATEGORY], longest first."""
    if not spans:
        return text
    categories: dict[str, str] = {}
    for span in spans:
        categories.setdefault(span.text, span.category)
    pattern = _boundary(sorted(categories, key=len, reverse=True))
    return pattern.sub(lambda match: f"[{categories[match.group()].upper()}]", text)


def _boundary(values: list[str]) -> re.Pattern[str]:
    # A value only counts as a whole token, so "Ana" never matches inside "Bananas".
    alternatives = "|".join(re.escape(value) for value in values)
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)")


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0
