import base64
import io
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageOps

from dsc_backend.errors import PipelineError
from dsc_backend.regions import Region

# Fills are RGBA. Outlines are opaque so a boxes-only fallback stays visible.
_FILL = {
    "stamp": (220, 38, 38, 110),
    "signature": (37, 99, 235, 110),
    "photograph": (234, 88, 12, 110),
    "rectangle": (22, 163, 74, 90),
}
_OUTLINE = {
    "stamp": (185, 28, 28, 255),
    "signature": (29, 78, 216, 255),
    "photograph": (194, 65, 12, 255),
    "rectangle": (21, 128, 61, 255),
}
_DEFAULT_FILL = (124, 58, 237, 110)
_DEFAULT_OUTLINE = (109, 40, 217, 255)


@dataclass(frozen=True)
class PreparedImage:
    image: Image.Image
    data_url: str


def prepare_image(image_bytes: bytes, content_type: str, max_edge: int) -> PreparedImage:
    """Decode a JPEG or PNG, apply EXIF orientation, and cap the long edge.

    The returned image is the one sent to SAM and Muse, so overlay coordinates
    match the pixels the models saw.
    """
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "image/jpg":
        media_type = "image/jpeg"
    if media_type not in {"image/jpeg", "image/png"}:
        raise PipelineError(400, "Only JPEG and PNG images are accepted")

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
        decoded_format = image.format
        image = ImageOps.exif_transpose(image)
    except Exception as exc:
        raise PipelineError(400, "Upload is not a valid JPEG or PNG image") from exc

    if decoded_format == "JPEG" and media_type != "image/jpeg":
        raise PipelineError(400, "Only JPEG and PNG images are accepted")
    if decoded_format == "PNG" and media_type != "image/png":
        raise PipelineError(400, "Only JPEG and PNG images are accepted")
    if decoded_format not in {"JPEG", "PNG"}:
        raise PipelineError(400, "Only JPEG and PNG images are accepted")

    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGBA" if image.format == "PNG" else "RGB")

    image = _limit_edge(image, max_edge)
    encoded, mime = _encode(image)
    payload = base64.b64encode(encoded).decode("ascii")
    return PreparedImage(image=image, data_url=f"data:{mime};base64,{payload}")


def render_overlay(image: Image.Image, regions: list[Region]) -> bytes:
    """Draw each mask at its box origin, scaled to the box, then outline the box."""
    base = image.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    for region in regions:
        raster_image = _raster_image(region)
        if raster_image is None:
            continue
        scaled = raster_image.resize((region.w, region.h), Image.Resampling.NEAREST)
        layer.paste(scaled, (region.x, region.y), scaled)

    composed = Image.alpha_composite(base, layer)
    stroke = 2 if min(base.size) >= 16 else 1
    draw = ImageDraw.Draw(composed)
    for region in regions:
        outline = _OUTLINE.get(region.label, _DEFAULT_OUTLINE)
        draw.rectangle(
            (region.x, region.y, region.x + region.w - 1, region.y + region.h - 1),
            outline=outline,
            width=stroke,
        )

    buffer = io.BytesIO()
    composed.save(buffer, format="PNG")
    return buffer.getvalue()


def _limit_edge(image: Image.Image, max_edge: int) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= max_edge:
        return image
    scale = max_edge / longest
    resized = image.resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        Image.Resampling.LANCZOS,
    )
    return resized


def _encode(image: Image.Image) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    if image.mode == "RGBA" or "A" in image.getbands():
        image.save(buffer, format="PNG")
        return buffer.getvalue(), "image/png"
    rgb = image.convert("RGB")
    rgb.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue(), "image/jpeg"


def _raster_image(region: Region) -> Image.Image | None:
    if region.raster is None or region.mask_width <= 0 or region.mask_height <= 0:
        return None
    expected = region.mask_width * region.mask_height
    if len(region.raster) != expected:
        return None
    color = _FILL.get(region.label, _DEFAULT_FILL)
    pixels = bytearray(expected * 4)
    red, green, blue, alpha = color
    for index, value in enumerate(region.raster):
        if not value:
            continue
        offset = index * 4
        pixels[offset : offset + 4] = bytes((red, green, blue, alpha))
    return Image.frombytes("RGBA", (region.mask_width, region.mask_height), bytes(pixels))
