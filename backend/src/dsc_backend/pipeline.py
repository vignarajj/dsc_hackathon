import asyncio
import base64
import logging
from collections.abc import Awaitable
from dataclasses import dataclass, field

from dsc_backend.config import DEFAULT_CONCEPTS, Settings
from dsc_backend.errors import PipelineError
from dsc_backend.imaging import prepare_image, render_overlay
from dsc_backend.meta import MetaGateway
from dsc_backend.privacy import Span, mask_text, merge_spans, occurs, pattern_spans, surnames
from dsc_backend.redaction import REDACT_STYLES, render_redacted
from dsc_backend.regions import Region, clamp_box

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int
    label: str
    score: float | None


@dataclass(frozen=True)
class ProcessResult:
    boxes: list[Box]
    overlay_png_base64: str
    original_text: str
    cleaned_text: str
    models: dict[str, str]
    redacted_png_base64: str | None = None
    sensitive: list[Span] = field(default_factory=list)
    shareable_text: str | None = None
    image_text_hidden: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Redaction:
    labels: tuple[str, ...] = ()
    style: str = "black"
    text: bool = False


_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off", ""}


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
    labels = concepts_for_request(raw_labels or "", DEFAULT_CONCEPTS)
    missing = [label for label in labels if label not in concepts]
    if missing:
        raise PipelineError(
            400,
            f"Only marked regions can be hidden. Mark {missing[0]} as well, or stop hiding it.",
        )
    style = (raw_style or "black").strip().lower()
    if style not in REDACT_STYLES:
        raise PipelineError(400, "Hidden regions can be black or blur.")
    flag = (raw_text or "").strip().lower()
    if flag not in _TRUE | _FALSE:
        raise PipelineError(400, "redact_text must be true or false.")
    return Redaction(labels=labels, style=style, text=flag in _TRUE)


async def process_image(
    image_bytes: bytes,
    content_type: str,
    gateway: MetaGateway,
    settings: Settings,
    concepts: tuple[str, ...] | None = None,
    redaction: Redaction | None = None,
) -> ProcessResult:
    prepared = prepare_image(image_bytes, content_type, settings.max_image_edge)
    selected = settings.sam_concepts if concepts is None else concepts
    hide = redaction or Redaction()
    width, height = prepared.image.size
    warnings: list[str] = []
    signature_task = None
    try:
        async with asyncio.TaskGroup() as group:
            segment_tasks = [
                group.create_task(gateway.segment(prepared.data_url, concept))
                for concept in selected
            ]
            transcript_task = group.create_task(gateway.transcribe(prepared.data_url))
            if "signature" in selected:
                signature_task = group.create_task(
                    _optional(gateway.signatures(prepared.data_url, width, height))
                )
    except ExceptionGroup as group:
        raise _from_group(group) from group

    muse_signatures: list[Region] = []
    signatures_failed = False
    if signature_task is not None:
        found = signature_task.result()
        if found is None:
            signatures_failed = True
            warnings.append(
                "Signatures could not be located, so none are "
                + ("marked or hidden." if "signature" in hide.labels else "marked.")
            )
        else:
            muse_signatures = found

    regions: list[Region] = []
    boxes: list[Box] = []
    for concept, task in zip(selected, segment_tasks, strict=True):
        found_regions = task.result()
        if concept == "signature":
            found_regions = found_regions + _new_regions(muse_signatures, found_regions)
        for region in found_regions:
            # Report the part of the box on the working image; drop boxes off it.
            clamped = clamp_box(region.x, region.y, region.w, region.h, width, height)
            if clamped is None:
                continue
            x, y, w, h = clamped
            regions.append(region)
            boxes.append(Box(x=x, y=y, w=w, h=h, label=region.label, score=region.score))
    original_text = transcript_task.result().strip()
    model_task = None
    try:
        async with asyncio.TaskGroup() as group:
            proofread_task = group.create_task(_proofread(gateway, original_text))
            if hide.text and original_text:
                model_task = group.create_task(_optional(gateway.sensitive_spans(original_text)))
    except ExceptionGroup as group:
        raise _from_group(group) from group
    cleaned_text = proofread_task.result()
    overlay = render_overlay(prepared.image, regions)

    sensitive: list[Span] = []
    shareable_text: str | None = None
    if hide.text:
        sensitive, shareable_text = _mask_sensitive(
            original_text, cleaned_text, model_task.result() if model_task else [], warnings
        )

    text_boxes: list[tuple[int, int, int, int]] | None = None
    if hide.text and settings.redact_image_text and sensitive:
        text_boxes = await _locate_text(gateway, prepared.data_url, width, height, sensitive)
        if text_boxes is None:
            warnings.append("Text in the picture could not be located, so it is not hidden.")
        elif len(text_boxes) < len(_lines(sensitive)):
            warnings.append(
                "Some sensitive text was not found in the picture, so it is not hidden there."
            )

    redacted: bytes | None = None
    if hide.labels or text_boxes is not None:
        boxes_found = [box for found in (text_boxes or {}).values() for box in found]
        redacted, hidden = render_redacted(
            prepared.image, regions, hide.labels, hide.style, boxes_found
        )
        for label in hide.labels:
            if label == "signature" and signatures_failed:
                continue
            if not any(region.label == label for region in regions):
                warnings.append(f"No {label} was found, so none is hidden.")
    else:
        hidden = 0
    logger.info(
        "processed concepts=%s boxes=%s hidden=%s text_chars=%s",
        ",".join(selected) or "-",
        len(regions),
        hidden,
        len(original_text),
    )
    return ProcessResult(
        boxes=boxes,
        overlay_png_base64=base64.b64encode(overlay).decode("ascii"),
        original_text=original_text,
        cleaned_text=cleaned_text,
        models={
            "segmentation": settings.sam_model,
            "transcription": settings.muse_vision_model,
            "proofread": settings.muse_text_model,
            "signatures": settings.muse_signature_model,
            **({"text_boxes": settings.muse_text_box_model} if settings.redact_image_text else {}),
        },
        redacted_png_base64=(
            base64.b64encode(redacted).decode("ascii") if redacted is not None else None
        ),
        sensitive=sensitive,
        shareable_text=shareable_text,
        image_text_hidden=text_boxes is not None,
        warnings=warnings,
    )


def _lines(spans: list[Span]) -> list[str]:
    """Each distinct line of span text. A word box covers one line at most."""
    lines: list[str] = []
    for span in spans:
        for line in span.text.splitlines():
            line = line.strip()
            if line and line not in lines:
                lines.append(line)
    return lines


async def _locate_text(
    gateway: MetaGateway,
    data_url: str,
    width: int,
    height: int,
    spans: list[Span],
) -> dict[str, list[tuple[int, int, int, int]]] | None:
    return await _optional(gateway.text_boxes(data_url, width, height, _lines(spans)))


def _mask_sensitive(
    original_text: str,
    cleaned_text: str,
    model: list[Span] | None,
    warnings: list[str],
) -> tuple[list[Span], str]:
    """Combine Muse and pattern spans, then mask them in the proofread text.

    Spans come from the transcript, because Muse reads it while the proofread
    runs. A span the proofread reworded cannot be masked, and the page is told.
    """
    if model is None:
        warnings.append(
            "Muse could not check the text for personal details, so only phone numbers, "
            "emails, and account numbers are masked."
        )
    from_transcript = pattern_spans(original_text)
    known = {span.text for span in from_transcript}
    patterns = from_transcript + [
        span for span in pattern_spans(cleaned_text) if span.text not in known
    ]
    spans = merge_spans(model or [], patterns)
    spans += surnames(spans, cleaned_text)
    if any(not occurs(cleaned_text, span.text) for span in spans):
        warnings.append(
            "Some sensitive text could not be matched after proofreading. "
            "Check the shareable text before you send it."
        )
    return spans, mask_text(cleaned_text, spans)


async def _optional[T](call: Awaitable[T]) -> T | None:
    """Run a step whose failure should not fail the request."""
    try:
        return await call
    except Exception as exc:
        logger.warning("optional step failed: %s", type(exc).__name__)
        return None


def _new_regions(candidates: list[Region], existing: list[Region]) -> list[Region]:
    """Keep the candidates that do not repeat a region already found."""
    return [
        region
        for region in candidates
        if not any(_overlap(region, other) >= 0.3 for other in existing)
    ]


def _overlap(a: Region, b: Region) -> float:
    """Intersection over union of two boxes."""
    width = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    height = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    if width <= 0 or height <= 0:
        return 0.0
    inter = width * height
    return inter / (a.w * a.h + b.w * b.h - inter)


async def _proofread(gateway: MetaGateway, original_text: str) -> str:
    if not original_text:
        return ""
    try:
        return (await gateway.proofread(original_text)).strip()
    except PipelineError:
        raise
    except TimeoutError as exc:
        raise PipelineError(502, "The model request timed out") from exc
    except Exception as exc:
        raise PipelineError(502, "The model request failed") from exc


def _from_group(group: ExceptionGroup[Exception]) -> PipelineError:
    for exc in group.exceptions:
        if isinstance(exc, PipelineError):
            return exc
        if isinstance(exc, ExceptionGroup):
            return _from_group(exc)
        if isinstance(exc, TimeoutError):
            return PipelineError(502, "The model request timed out")
    return PipelineError(502, "The model request failed")
