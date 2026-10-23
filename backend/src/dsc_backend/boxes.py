import json
import math
import re

from dsc_backend.regions import clamp_box

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def load_json_object(text: str) -> dict[str, object] | None:
    """Read the JSON object in a model reply, allowing a Markdown fence around it."""
    body = text.strip()
    fenced = _FENCE.search(body)
    if fenced:
        body = fenced.group(1).strip()
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(body[start : end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def pixel_box(
    value: object,
    width: int,
    height: int,
    pad_x: float = 0.0,
    pad_y: float = 0.0,
) -> tuple[int, int, int, int] | None:
    """Turn a model's [x1, y1, x2, y2] into a clipped (x, y, w, h).

    pad_x and pad_y widen the box by that share of its own width and height on
    each side. Muse boxes land a few pixels off, and a hidden region must cover
    the whole mark.
    """
    if not isinstance(value, list) or len(value) != 4:
        return None
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in value):
        return None
    x1, y1, x2, y2 = (float(v) for v in value)
    if not all(math.isfinite(v) for v in (x1, y1, x2, y2)) or x2 <= x1 or y2 <= y1:
        return None
    box_w, box_h = x2 - x1, y2 - y1
    left = math.floor(x1 - box_w * pad_x)
    top = math.floor(y1 - box_h * pad_y)
    right = math.ceil(x2 + box_w * pad_x)
    bottom = math.ceil(y2 + box_h * pad_y)
    return clamp_box(left, top, right - left, bottom - top, width, height)
