import asyncio
from dataclasses import dataclass

from PIL import Image

from dsc_backend.describe import (
    CONCURRENCY,
    MAX_DESCRIBED,
    clean_description,
    crop_region,
    describe_order,
    describe_regions,
)


@dataclass
class B:
    x: int
    y: int
    w: int
    h: int
    score: float | None = None


def test_crop_adds_a_margin_and_clips_to_the_image() -> None:
    image = Image.new("RGB", (1000, 1000))
    crop = crop_region(image, B(400, 400, 300, 300))
    assert crop is not None
    # 8% of 300 is 24 a side.
    assert crop.size == (348, 348)
    # Off the right and bottom edges: 976 - 876 = 100 px left, then enlarged to 256.
    edge = crop_region(image, B(900, 900, 300, 300))
    assert edge is not None and edge.size == (256, 256)


def test_small_crops_are_enlarged_without_a_huge_long_side() -> None:
    image = Image.new("RGB", (2000, 2000))
    small = crop_region(image, B(100, 100, 50, 40))
    assert small is not None
    assert min(small.size) == 256
    # A thin strip is enlarged only until its long side reaches 1536 px.
    thin = crop_region(image, B(100, 100, 600, 20))
    assert thin is not None
    assert max(thin.size) == 1536
    assert min(thin.size) < 256
    assert crop_region(image, B(3000, 3000, 10, 10)) is None


def test_order_is_best_score_first_unscored_last_and_capped() -> None:
    assert describe_order([0.2, None, 0.9, 0.5]) == [2, 3, 0, 1]
    assert len(describe_order([0.5] * 12)) == MAX_DESCRIBED


def test_descriptions_are_one_short_line() -> None:
    assert (
        clean_description("  Round red stamp\n reading 'PAID' ") == "Round red stamp reading 'PAID'"
    )
    assert clean_description("   ") is None
    long = clean_description("word " * 60)
    assert long is not None and len(long) <= 160 and long.endswith("…")


def test_regions_are_described_four_at_a_time_and_failures_stay_local() -> None:
    image = Image.new("RGB", (800, 800), (200, 200, 200))
    boxes = [B(10 * i, 10 * i, 60, 60, score=i / 10) for i in range(10)]
    running = 0
    peak = 0
    seen: list[str] = []

    async def describe(data_url: str) -> str:
        nonlocal running, peak
        assert data_url.startswith("data:image/jpeg;base64,")
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        seen.append(data_url)
        if len(seen) == 2:
            raise RuntimeError("one crop fails")
        return "A grey square"

    notes = asyncio.run(describe_regions(image, boxes, describe))
    assert peak == CONCURRENCY
    assert len(seen) == MAX_DESCRIBED
    # The two lowest scores are left out; one call failed.
    assert notes[0] is None and notes[1] is None
    assert sum(note == "A grey square" for note in notes) == MAX_DESCRIBED - 1
    assert sum(note is None for note in notes[2:]) == 1
