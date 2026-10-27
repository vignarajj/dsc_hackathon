import asyncio
import base64
import logging
from dataclasses import dataclass, field, replace

from dsc_backend.budget import Budget
from dsc_backend.config import Settings
from dsc_backend.describe import describe_regions
from dsc_backend.errors import PipelineError
from dsc_backend.extraction import Document, InvalidDocument, parse_document
from dsc_backend.form import Redaction
from dsc_backend.imaging import (
    Colors,
    PreparedImage,
    palette,
    region_colors,
    render_overlay,
)
from dsc_backend.meta import MetaGateway
from dsc_backend.privacy import Span, mask_text, merge_spans, occurs, pattern_spans, surnames
from dsc_backend.progress import Emit, Progress
from dsc_backend.redaction import render_redacted
from dsc_backend.regions import Region, clamp_box

logger = logging.getLogger(__name__)

# Names of the optional steps, as the budget warning shows them.
_SIGNATURES = "Finding signatures"
_DESCRIBE = "Describing regions"
_EXTRACT = "Pulling out key fields"
_PRIVACY = "Finding personal details"
_TEXT_BOXES = "Finding text in the picture"


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int
    label: str
    score: float | None
    description: str | None = None


@dataclass(frozen=True)
class ProcessResult:
    boxes: list[Box]
    overlay_png_base64: str
    original_text: str
    cleaned_text: str
    models: dict[str, str]
    palette: dict[str, str] = field(default_factory=dict)
    redacted_png_base64: str | None = None
    sensitive: list[Span] = field(default_factory=list)
    shareable_text: str | None = None
    image_text_hidden: bool = False
    document: Document | None = None
    warnings: list[str] = field(default_factory=list)


async def process_image(
    prepared: PreparedImage,
    gateway: MetaGateway,
    settings: Settings,
    concepts: tuple[str, ...] | None = None,
    redaction: Redaction | None = None,
    extract: bool = False,
    emit: Emit | None = None,
    describe: bool = False,
) -> ProcessResult:
    """Run every step on an image already checked by prepare_image.

    emit, when given, receives an event as each stage starts and finishes.
    """
    selected = settings.sam_concepts if concepts is None else concepts
    hide = redaction or Redaction()
    width, height = prepared.image.size
    warnings: list[str] = []
    if extract and not settings.feature_extract:
        extract = False
        warnings.append("Key fields are turned off on this server.")
    if describe and not settings.feature_describe:
        describe = False
        warnings.append("Region descriptions are turned off on this server.")
    muse_privacy = hide.text and settings.feature_privacy
    if hide.text and not muse_privacy:
        warnings.append(
            "The Muse check for personal details is turned off on this server, so only "
            "phone numbers, emails, and account numbers are masked."
        )
    budget = Budget(settings.request_budget_seconds)
    progress = Progress(emit)
    await progress.plan(
        ["prepare"]
        + (["segment"] if selected else [])
        + (["describe"] if selected and describe else [])
        + ["transcribe", "proofread"]
        + (["extract"] if extract else [])
        + (["privacy"] if hide.text else [])
        + ["render"]
    )
    await progress.done("prepare", f"{width}x{height}")

    segment_task = None
    describe_task = None
    try:
        async with asyncio.TaskGroup() as group:
            if selected:
                segment_task = group.create_task(
                    progress.run(
                        "segment",
                        _segment(gateway, prepared.data_url, selected, width, height, budget),
                        lambda found: _region_summary(selected, found[0]),
                    )
                )
            if segment_task is not None and describe:
                # Starts as soon as SAM is done, while the transcription may still run.
                describe_task = group.create_task(
                    progress.run(
                        "describe",
                        budget.optional(
                            _describe_after(segment_task, gateway, prepared, width, height),
                            _DESCRIBE,
                        ),
                        _described_summary,
                    )
                )
            transcript_task = group.create_task(
                progress.run(
                    "transcribe",
                    gateway.transcribe(prepared.data_url),
                    lambda text: f"{len(text.strip())} characters",
                )
            )
    except ExceptionGroup as group:
        raise _from_group(group) from group

    found_by_concept, signatures_failed = segment_task.result() if segment_task else ([], False)
    if signatures_failed and not budget.was_cut(_SIGNATURES):
        warnings.append(
            "Signatures could not be located, so none are "
            + ("marked or hidden." if "signature" in hide.labels else "marked.")
        )
    kept = _on_image(found_by_concept, width, height)
    regions = [region for region, _ in kept]
    boxes = [box for _, box in kept]
    notes = describe_task.result() if describe_task is not None else None
    if notes is not None:
        boxes = [replace(box, description=note) for box, note in zip(boxes, notes, strict=True)]
    original_text = transcript_task.result().strip()

    model_task = None
    extract_task = None
    try:
        async with asyncio.TaskGroup() as group:
            proofread_task = group.create_task(
                progress.run("proofread", _proofread(gateway, original_text))
            )
            if hide.text:
                model_task = group.create_task(
                    progress.run(
                        "privacy",
                        budget.optional(gateway.sensitive_spans(original_text), _PRIVACY)
                        if original_text and muse_privacy
                        else _nothing([]),
                    )
                )
            if extract:
                extract_task = group.create_task(
                    progress.run(
                        "extract",
                        budget.optional(_extract(gateway, original_text), _EXTRACT)
                        if original_text
                        else _nothing(""),
                    )
                )
    except ExceptionGroup as group:
        raise _from_group(group) from group
    cleaned_text = proofread_task.result()

    document: Document | None = None
    if extract_task is not None and original_text:
        reply = extract_task.result()
        if reply is None:
            if not budget.was_cut(_EXTRACT):
                warnings.append("Muse could not pull out the document's fields.")
        else:
            # Checked against both texts, since the proofread may fix a misread value.
            document = parse_document(reply, original_text, cleaned_text)

    sensitive: list[Span] = []
    shareable_text: str | None = None
    if hide.text:
        spans = model_task.result() if model_task else []
        if spans is None and budget.was_cut(_PRIVACY):
            spans = []  # The budget warning says it was skipped; the patterns still run.
        sensitive, shareable_text = _mask_sensitive(original_text, cleaned_text, spans, warnings)

    colors = region_colors(selected)
    overlay, redacted, text_boxes, hidden = await progress.run(
        "render",
        _render(
            gateway,
            settings,
            prepared,
            regions,
            hide,
            sensitive,
            colors,
            signatures_failed,
            warnings,
            budget,
        ),
    )
    warnings.extend(budget.warnings())
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
            **({"extraction": settings.muse_text_model} if extract else {}),
            **({"text_boxes": settings.muse_text_box_model} if settings.redact_image_text else {}),
        },
        palette=palette(colors),
        redacted_png_base64=(
            base64.b64encode(redacted).decode("ascii") if redacted is not None else None
        ),
        sensitive=sensitive,
        shareable_text=shareable_text,
        image_text_hidden=text_boxes is not None,
        document=document,
        warnings=warnings,
    )


def _on_image(
    found_by_concept: list[list[Region]], width: int, height: int
) -> list[tuple[Region, Box]]:
    """Each region with its box clipped to the working image. Boxes off it are dropped."""
    kept: list[tuple[Region, Box]] = []
    for found_regions in found_by_concept:
        for region in found_regions:
            clamped = clamp_box(region.x, region.y, region.w, region.h, width, height)
            if clamped is None:
                continue
            x, y, w, h = clamped
            kept.append((region, Box(x=x, y=y, w=w, h=h, label=region.label, score=region.score)))
    return kept


async def _describe_after(
    segment_task: asyncio.Task[tuple[list[list[Region]], bool]],
    gateway: MetaGateway,
    prepared: PreparedImage,
    width: int,
    height: int,
) -> list[str | None]:
    found_by_concept, _ = await segment_task
    boxes = [box for _, box in _on_image(found_by_concept, width, height)]
    return await describe_regions(prepared.image, boxes, gateway.describe_region)


def _described_summary(notes: list[str | None] | None) -> str:
    if notes is None:
        return "skipped"
    return f"{sum(note is not None for note in notes)} of {len(notes)} described"


async def _segment(
    gateway: MetaGateway,
    data_url: str,
    selected: tuple[str, ...],
    width: int,
    height: int,
    budget: Budget,
) -> tuple[list[list[Region]], bool]:
    """SAM for every concept and, for signatures, Muse boxes too, all at once.

    Returns the regions for each concept in order, and whether the Muse
    signature lookup failed.
    """
    signature_task = None
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(gateway.segment(data_url, concept)) for concept in selected]
        if "signature" in selected:
            signature_task = group.create_task(
                budget.optional(gateway.signatures(data_url, width, height), _SIGNATURES)
            )
    muse_signatures = signature_task.result() if signature_task else []
    found: list[list[Region]] = []
    for concept, task in zip(selected, tasks, strict=True):
        regions = task.result()
        if concept == "signature" and muse_signatures:
            regions = regions + _new_regions(muse_signatures, regions)
        found.append(regions)
    return found, signature_task is not None and muse_signatures is None


async def _render(
    gateway: MetaGateway,
    settings: Settings,
    prepared: PreparedImage,
    regions: list[Region],
    hide: Redaction,
    sensitive: list[Span],
    colors: Colors,
    signatures_failed: bool,
    warnings: list[str],
    budget: Budget,
) -> tuple[bytes, bytes | None, dict[str, list[tuple[int, int, int, int]]] | None, int]:
    """Draw the overlay and build the share-safe copy."""
    width, height = prepared.image.size
    overlay = render_overlay(prepared.image, regions, colors)
    text_boxes = None
    if hide.text and settings.redact_image_text and sensitive:
        text_boxes = await budget.optional(
            gateway.text_boxes(prepared.data_url, width, height, _lines(sensitive)), _TEXT_BOXES
        )
        if text_boxes is None and not budget.was_cut(_TEXT_BOXES):
            warnings.append("Text in the picture could not be located, so it is not hidden.")
        elif len(text_boxes) < len(_lines(sensitive)):
            warnings.append(
                "Some sensitive text was not found in the picture, so it is not hidden there."
            )
    if not hide.labels and text_boxes is None:
        return overlay, None, None, 0
    boxes_found = [box for found in (text_boxes or {}).values() for box in found]
    redacted, hidden = render_redacted(
        prepared.image, regions, hide.labels, hide.style, boxes_found
    )
    for label in hide.labels:
        if label == "signature" and signatures_failed:
            continue
        if not any(region.label == label for region in regions):
            warnings.append(f"No {label} was found, so none is hidden.")
    return overlay, redacted, text_boxes, hidden


def _region_summary(selected: tuple[str, ...], found: list[list[Region]]) -> str:
    return ", ".join(f"{concept}: {len(regions)}" for concept, regions in zip(selected, found))


async def _nothing[T](value: T) -> T:
    return value


async def _extract(gateway: MetaGateway, transcript: str) -> str:
    """Ask for the document as data, with one repair prompt if the JSON is unusable.

    The repair is a second prompt naming the problem, not a retry of a failed
    call. Two unusable answers raise, which the caller turns into a warning.
    """
    reply = await gateway.extract(transcript)
    try:
        parse_document(reply, transcript)
    except InvalidDocument as problem:
        reply = await gateway.extract(transcript, str(problem))
        parse_document(reply, transcript)
    return reply


def _lines(spans: list[Span]) -> list[str]:
    """Each distinct line of span text. A word box covers one line at most."""
    lines: list[str] = []
    for span in spans:
        for line in span.text.splitlines():
            line = line.strip()
            if line and line not in lines:
                lines.append(line)
    return lines


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
