import asyncio
import base64
import logging
from dataclasses import dataclass

from dsc_backend.config import DEFAULT_CONCEPTS, Settings
from dsc_backend.errors import PipelineError
from dsc_backend.imaging import prepare_image, render_overlay
from dsc_backend.meta import MetaGateway

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


async def process_image(
    image_bytes: bytes,
    content_type: str,
    gateway: MetaGateway,
    settings: Settings,
    concepts: tuple[str, ...] | None = None,
) -> ProcessResult:
    prepared = prepare_image(image_bytes, content_type, settings.max_image_edge)
    selected = settings.sam_concepts if concepts is None else concepts
    try:
        async with asyncio.TaskGroup() as group:
            segment_tasks = [
                group.create_task(gateway.segment(prepared.data_url, concept))
                for concept in selected
            ]
            transcript_task = group.create_task(gateway.transcribe(prepared.data_url))
    except ExceptionGroup as group:
        raise _from_group(group) from group

    regions = [region for task in segment_tasks for region in task.result()]
    original_text = transcript_task.result().strip()
    cleaned_text = await _proofread(gateway, original_text)
    overlay = render_overlay(prepared.image, regions)
    logger.info(
        "processed concepts=%s boxes=%s text_chars=%s",
        ",".join(selected) or "-",
        len(regions),
        len(original_text),
    )
    return ProcessResult(
        boxes=[
            Box(
                x=region.x,
                y=region.y,
                w=region.w,
                h=region.h,
                label=region.label,
                score=region.score,
            )
            for region in regions
        ],
        overlay_png_base64=base64.b64encode(overlay).decode("ascii"),
        original_text=original_text,
        cleaned_text=cleaned_text,
    )


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
