import re
from dataclasses import dataclass

from dsc_backend.boxes import load_json_object

DOC_TYPES = (
    "invoice",
    "receipt",
    "form",
    "id_document",
    "letter",
    "chat",
    "note",
    "screenshot",
    "other",
)
MAX_FIELDS = 20
MAX_LABEL_CHARS = 40
MAX_VALUE_CHARS = 200
_MAX_TITLE_CHARS = 120
_MAX_SUMMARY_CHARS = 400

EXTRACT_FORMAT = {
    "type": "json_schema",
    "name": "document",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["type", "title", "summary", "fields"],
        "properties": {
            "type": {"type": "string", "enum": list(DOC_TYPES)},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["label", "value"],
                    "properties": {
                        "label": {"type": "string"},
                        "value": {"type": "string"},
                    },
                },
            },
        },
    },
}


@dataclass(frozen=True)
class Field:
    label: str
    value: str
    found_in_text: bool


@dataclass(frozen=True)
class Document:
    type: str
    title: str
    summary: str
    fields: list[Field]


class InvalidDocument(ValueError):
    """The reply was not the document JSON. The message says why, for the repair prompt."""


def parse_document(reply: str, *texts: str) -> Document:
    """Validate Muse's reply and mark which values really appear in the text."""
    data = load_json_object(reply)
    if data is None:
        raise InvalidDocument("The reply was not a JSON object.")
    doc_type = data.get("type")
    if doc_type not in DOC_TYPES:
        raise InvalidDocument(f"type must be one of: {', '.join(DOC_TYPES)}.")
    title, summary = data.get("title"), data.get("summary")
    if not isinstance(title, str) or not isinstance(summary, str):
        raise InvalidDocument("title and summary must be strings.")
    items = data.get("fields")
    if not isinstance(items, list):
        raise InvalidDocument("fields must be a list.")
    haystacks = [normalize(text) for text in texts]
    fields: list[Field] = []
    for item in items:
        if len(fields) == MAX_FIELDS:
            break
        if not isinstance(item, dict):
            raise InvalidDocument("each field must be an object with label and value.")
        label, value = item.get("label"), item.get("value")
        if not isinstance(label, str) or not isinstance(value, str):
            raise InvalidDocument("each field label and value must be a string.")
        label, value = label.strip(), value.strip()
        if not label or not value or len(label) > MAX_LABEL_CHARS or len(value) > MAX_VALUE_CHARS:
            continue
        needle = normalize(value)
        found = bool(needle) and any(needle in haystack for haystack in haystacks)
        fields.append(Field(label=label, value=value, found_in_text=found))
    return Document(
        type=doc_type,
        title=title.strip()[:_MAX_TITLE_CHARS],
        summary=summary.strip()[:_MAX_SUMMARY_CHARS],
        fields=fields,
    )


def normalize(text: str) -> str:
    """Lowercase letters and digits only, so case, spacing, and punctuation never matter."""
    return re.sub(r"[\W_]+", "", text.lower())
