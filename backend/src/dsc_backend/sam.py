import logging
from collections.abc import Iterable, Sequence

from meta_sam_parser import (
    SegmentationBoxRecord,
    SegmentationMaskRecord,
    decode_mask_to_raster,
)

from dsc_backend.errors import PipelineError
from dsc_backend.regions import Region

logger = logging.getLogger(__name__)


def regions_from_records(records: Iterable[object], label: str) -> list[Region]:
    """Pair each SAM box with its mask. A box without a decodable mask is kept."""
    boxes: dict[str, SegmentationBoxRecord] = {}
    masks: dict[str, SegmentationMaskRecord] = {}
    for record in records:
        kind = getattr(record, "kind", None)
        if kind == "box":
            boxes[record.object_id] = record
        elif kind == "mask":
            masks[record.object_id] = record

    regions: list[Region] = []
    for object_id, box in boxes.items():
        x = _pixel(box.left)
        y = _pixel(box.top)
        width = _pixel(box.right) - x
        height = _pixel(box.bottom) - y
        if width <= 0 or height <= 0:
            continue
        raster, mask_width, mask_height = _decode_mask(masks.get(object_id), label, object_id)
        regions.append(
            Region(
                x=x,
                y=y,
                w=width,
                h=height,
                label=label,
                score=box.confidence,
                raster=raster,
                mask_width=mask_width,
                mask_height=mask_height,
            )
        )
    return regions


def ensure_completed(result: object, concept: str) -> Sequence[object]:
    outcome = getattr(result, "outcome", None)
    status = getattr(outcome, "status", None)
    if status != "completed":
        logger.error("SAM concept %s outcome=%s", concept, status)
        raise PipelineError(502, "The model request failed")
    diagnostics = getattr(result, "diagnostics", ())
    errors = [item for item in diagnostics if getattr(item, "severity", None) == "error"]
    if errors:
        logger.error("SAM concept %s parser errors=%s", concept, len(errors))
        raise PipelineError(502, "The model request failed")
    records = getattr(result, "records", ())
    return records


def _decode_mask(
    mask: SegmentationMaskRecord | None,
    label: str,
    object_id: str,
) -> tuple[bytes | None, int, int]:
    if mask is None:
        return None, 0, 0
    try:
        decoded = decode_mask_to_raster(mask.mask)
    except Exception:
        logger.warning("mask decode failed label=%s object_id=%s", label, object_id)
        return None, 0, 0
    width = mask.mask.width
    height = mask.mask.height
    if len(decoded) != width * height:
        logger.warning("mask size mismatch label=%s object_id=%s", label, object_id)
        return None, 0, 0
    return bytes(decoded), width, height


def _pixel(value: float) -> int:
    return int(value)
