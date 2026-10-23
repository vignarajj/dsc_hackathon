import io
from collections.abc import Collection

from PIL import Image, ImageDraw, ImageFilter

from dsc_backend.imaging import region_mask
from dsc_backend.regions import Region, clamp_box

REDACT_STYLES = ("black", "blur")

# Grow every mask by this many pixels so anti-aliased edges do not show.
_DILATE_PX = 3


def hide_mask(
    size: tuple[int, int],
    regions: list[Region],
    labels: Collection[str],
) -> tuple[Image.Image, int]:
    """Build the L mask of everything to hide, and count the regions in it.

    A region follows its SAM mask, pasted at the box origin and scaled to the
    box. A region without a usable mask is hidden as its whole box, which is
    the safer choice.
    """
    width, height = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    hidden = 0
    for region in regions:
        if region.label not in labels:
            continue
        clamped = clamp_box(region.x, region.y, region.w, region.h, width, height)
        if clamped is None:
            continue
        hidden += 1
        alpha = region_mask(region)
        if alpha is None:
            x, y, w, h = clamped
            draw.rectangle((x, y, x + w - 1, y + h - 1), fill=255)
            continue
        scaled = alpha.resize((region.w, region.h), Image.Resampling.NEAREST)
        mask.paste(255, (region.x, region.y), scaled)
    if hidden:
        mask = mask.filter(ImageFilter.MaxFilter(_DILATE_PX * 2 + 1))
    return mask, hidden


def render_redacted(
    image: Image.Image,
    regions: list[Region],
    labels: Collection[str],
    style: str,
    text_boxes: list[tuple[int, int, int, int]] | None = None,
) -> tuple[bytes, int]:
    """Hide the chosen regions and return a PNG with no metadata.

    text_boxes are (x, y, w, h) areas that are always blacked out, whatever
    the style, because blurred text can still be read.
    """
    base = image.convert("RGB")
    mask, hidden = hide_mask(base.size, regions, labels)
    if style == "blur":
        _blur_into(base, mask, regions, labels)
    else:
        base.paste((0, 0, 0), (0, 0), mask)
    if text_boxes:
        draw = ImageDraw.Draw(base)
        for x, y, w, h in text_boxes:
            draw.rectangle((x, y, x + w - 1, y + h - 1), fill=(0, 0, 0))
    # Copy the pixels into a fresh image so no EXIF, GPS, or text chunk from
    # the upload can reach the file.
    clean = Image.frombytes("RGB", base.size, base.tobytes())
    buffer = io.BytesIO()
    clean.save(buffer, format="PNG")
    return buffer.getvalue(), hidden


def _blur_into(
    base: Image.Image,
    mask: Image.Image,
    regions: list[Region],
    labels: Collection[str],
) -> None:
    width, height = base.size
    for region in regions:
        if region.label not in labels:
            continue
        clamped = clamp_box(region.x, region.y, region.w, region.h, width, height)
        if clamped is None:
            continue
        x, y, w, h = clamped
        radius = max(8, min(w, h) // 4)
        # Blur a margin around the box too, so the edge pixels mix with
        # neighbours instead of with themselves.
        area = (
            max(0, x - radius - _DILATE_PX),
            max(0, y - radius - _DILATE_PX),
            min(width, x + w + radius + _DILATE_PX),
            min(height, y + h + radius + _DILATE_PX),
        )
        blurred = base.crop(area).filter(ImageFilter.GaussianBlur(radius))
        base.paste(blurred, area[:2], mask.crop(area))
