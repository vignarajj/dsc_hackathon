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
