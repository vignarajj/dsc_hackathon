from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    x: int
    y: int
    w: int
    h: int
    label: str
    score: float | None
    raster: bytes | None = None
    mask_width: int = 0
    mask_height: int = 0


def clamp_box(
    x: int, y: int, w: int, h: int, width: int, height: int
) -> tuple[int, int, int, int] | None:
    """Clip a box to the image. Returns None when nothing of it is left."""
    left = min(max(x, 0), width)
    top = min(max(y, 0), height)
    right = min(max(x + w, 0), width)
    bottom = min(max(y + h, 0), height)
    if right <= left or bottom <= top:
        return None
    return left, top, right - left, bottom - top
