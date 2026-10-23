import asyncio
import base64
import io
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from PIL import Image

from dsc_backend.regions import clamp_box

logger = logging.getLogger(__name__)

MAX_DESCRIBED = 8
CONCURRENCY = 4
_PAD = 0.08
_MIN_SIDE = 256
_MAX_SIDE = 1536
_MAX_CHARS = 160


class Placed(Protocol):
    x: int
    y: int
    w: int
    h: int
    score: float | None


def crop_region(image: Image.Image, box: Placed) -> Image.Image | None:
    """The box plus an 8% margin, clipped to the image, enlarged if it is small.

    Muse reads a small crop poorly, so the short side is brought up to 256 px,
    without letting the long side pass 1536 px.
    """
    width, height = image.size
    pad_x, pad_y = round(box.w * _PAD), round(box.h * _PAD)
    clamped = clamp_box(
        box.x - pad_x, box.y - pad_y, box.w + 2 * pad_x, box.h + 2 * pad_y, width, height
    )
    if clamped is None:
        return None
    x, y, w, h = clamped
    crop = image.convert("RGB").crop((x, y, x + w, y + h))
    if min(w, h) < _MIN_SIDE:
        scale = min(_MIN_SIDE / min(w, h), _MAX_SIDE / max(w, h))
        if scale > 1:
            crop = crop.resize(
                (max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS
            )
    return crop


def crop_data_url(crop: Image.Image) -> str:
    buffer = io.BytesIO()
    crop.save(buffer, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def describe_order(scores: Sequence[float | None], limit: int = MAX_DESCRIBED) -> list[int]:
    """The indexes to describe: best score first, unscored last, at most limit."""
    ranked = sorted(range(len(scores)), key=lambda i: _rank(scores[i]))
    return ranked[:limit]


def _rank(score: float | None) -> float:
    return float("inf") if score is None else -score


def clean_description(text: str) -> str | None:
    """One line, at most 160 characters, cut at a word. Empty means none."""
    line = " ".join(text.split())
    if len(line) > _MAX_CHARS:
        line = line[: _MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
    return line or None


async def describe_regions(
    image: Image.Image,
    boxes: Sequence[Placed],
    describe: Callable[[str], Awaitable[str]],
) -> list[str | None]:
    """Describe up to 8 boxes, 4 at a time. A failed box gets None; the rest carry on."""
    results: list[str | None] = [None] * len(boxes)
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(index: int) -> None:
        crop = crop_region(image, boxes[index])
        if crop is None:
            return
        async with gate:
            try:
                results[index] = clean_description(await describe(crop_data_url(crop)))
            except Exception as exc:
                logger.warning("region description failed: %s", type(exc).__name__)

    async with asyncio.TaskGroup() as group:
        for index in describe_order([box.score for box in boxes]):
            group.create_task(one(index))
    return results
