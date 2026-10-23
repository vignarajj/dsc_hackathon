import re
from dataclasses import dataclass

from dsc_backend.config import DEFAULT_CONCEPTS
from dsc_backend.errors import PipelineError
from dsc_backend.redaction import REDACT_STYLES

MAX_CUSTOM = 3

# Typed names that mean a preset region.
_ALIASES = {"photo": "photograph", "stamps": "stamp", "signatures": "signature"}
_CUSTOM = re.compile(r"^[a-z][a-z -]{0,29}$")
# Prompts for text found nothing in the Phase 0 and F0 spikes. SAM marks objects.
_BLOCKED = {
    "text",
    "document",
    "printed text",
    "receipt",
    "handwritten note",
    "handwriting",
    "handwritten text",
}
_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off", ""}


@dataclass(frozen=True)
class Redaction:
    labels: tuple[str, ...] = ()
    style: str = "black"
    text: bool = False


def concepts_for_request(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    """Turn the form field into SAM prompts.

    A missing field uses the server default. An empty field segments nothing.
    Names outside the known four are rejected so the client cannot invent prompts.
    """
    if raw is None:
        return default
    allowed = set(DEFAULT_CONCEPTS)
    chosen: set[str] = set()
    for part in raw.split(","):
        name = part.strip().lower()
        if not name:
            continue
        if name not in allowed:
            raise PipelineError(
                400,
                "Unknown region. Choose stamp, signature, photograph, or rectangle.",
            )
        chosen.add(name)
    return tuple(concept for concept in DEFAULT_CONCEPTS if concept in chosen)


def custom_concepts_for_request(raw: str | None, presets: tuple[str, ...]) -> tuple[str, ...]:
    """Add the user's own region names to the presets.

    Each name is 1 to 3 plain lowercase words. A name that means a preset turns
    that preset on, so "Stamp" never costs a second SAM call. Presets keep
    their order; custom names follow in the order typed.
    """
    if not raw:
        return presets
    chosen = set(presets)
    custom: list[str] = []
    for part in raw.split(","):
        name = _normal(part)
        if not name:
            continue
        name = _ALIASES.get(name, name)
        if name in DEFAULT_CONCEPTS:
            chosen.add(name)
            continue
        if not _CUSTOM.fullmatch(name) or len(name.split()) > 3:
            raise PipelineError(400, "Describe what to find in 1 to 3 plain words, like logo.")
        if name in _BLOCKED:
            raise PipelineError(400, "SAM marks objects, not text. Try a stamp, logo, or QR code.")
        if name not in custom:
            custom.append(name)
    if len(custom) > MAX_CUSTOM:
        raise PipelineError(400, f"Add up to {MAX_CUSTOM} things to find.")
    ordered = tuple(concept for concept in DEFAULT_CONCEPTS if concept in chosen)
    return ordered + tuple(custom)


def redaction_for_request(
    raw_labels: str | None,
    raw_style: str | None,
    concepts: tuple[str, ...],
    raw_text: str | None = None,
) -> Redaction:
    """Read which marked regions to hide, and how.

    Only regions that are also marked can be hidden, so the page never offers
    a share-safe copy built from regions nobody looked for.
    """
    wanted: set[str] = set()
    for part in (raw_labels or "").split(","):
        name = _normal(part)
        if not name:
            continue
        name = _ALIASES.get(name, name)
        if name not in concepts:
            raise PipelineError(
                400,
                f"Only marked regions can be hidden. Mark {name} as well, or stop hiding it.",
            )
        wanted.add(name)
    style = (raw_style or "black").strip().lower()
    if style not in REDACT_STYLES:
        raise PipelineError(400, "Hidden regions can be black or blur.")
    flag = (raw_text or "").strip().lower()
    if flag not in _TRUE | _FALSE:
        raise PipelineError(400, "redact_text must be true or false.")
    labels = tuple(concept for concept in concepts if concept in wanted)
    return Redaction(labels=labels, style=style, text=flag in _TRUE)


def _normal(name: str) -> str:
    return " ".join(name.lower().split())
