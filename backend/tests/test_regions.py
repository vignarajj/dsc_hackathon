import asyncio

from meta_sam_parser import (
    SegmentationBoxRecord,
    SegmentationMask,
    SegmentationMaskBounds,
    SegmentationMaskIdentity,
    SegmentationMaskRecord,
    image_segmentation_format,
    parse_responses_stream,
)

from dsc_backend.sam import regions_from_records

_LINE = (
    "<0f>0<|box;x1=211;y1=228;x2=270;y2=254;w=320;h=334;c=0.97|>"
    "<|mask;x=0;y=0;data=27,60,~!!!!M!0c[0o91w?q1!pIH4pPRVp2B3'7`e.ioeAf6-k/#Xd8%dX9x(|>"
)


def test_pairs_box_with_decoded_mask() -> None:
    mask = SegmentationMask(encoding="one_bit", payload="!!!!!(QO(0lu8?", width=5, height=5)
    records = [
        SegmentationBoxRecord(
            order=0,
            object_id="0",
            left=1,
            top=2,
            right=6,
            bottom=7,
            confidence=0.5,
        ),
        SegmentationMaskRecord(
            order=1,
            object_id="0",
            identity=SegmentationMaskIdentity(media="image", frame_index=None, object_id="0"),
            revision=0,
            mask=mask,
            bounds=SegmentationMaskBounds(left=1, top=2, right=6, bottom=7),
            confidence=0.5,
        ),
    ]
    regions = regions_from_records(records, "stamp")
    assert len(regions) == 1
    region = regions[0]
    assert (region.x, region.y, region.w, region.h, region.label, region.score) == (
        1,
        2,
        5,
        5,
        "stamp",
        0.5,
    )
    assert region.raster is not None
    assert len(region.raster) == 25
    assert any(region.raster)


def test_keeps_box_when_mask_payload_is_invalid() -> None:
    records = [
        SegmentationBoxRecord(
            order=0,
            object_id="0",
            left=0,
            top=0,
            right=4,
            bottom=4,
            confidence=None,
        ),
        SegmentationMaskRecord(
            order=1,
            object_id="0",
            identity=SegmentationMaskIdentity(media="image", frame_index=None, object_id="0"),
            revision=0,
            mask=SegmentationMask(encoding="one_bit", payload="not-a-mask", width=2, height=2),
            bounds=SegmentationMaskBounds(left=0, top=0, right=4, bottom=4),
        ),
    ]
    regions = regions_from_records(records, "signature")
    assert len(regions) == 1
    assert regions[0].raster is None
    assert regions[0].score is None


def test_parser_stream_becomes_regions() -> None:
    async def events():
        yield {
            "type": "response.output_text.delta",
            "delta": _LINE,
            "item_id": "item_1",
            "output_index": 0,
            "content_index": 0,
        }
        yield {
            "type": "response.content_part.done",
            "item_id": "item_1",
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": _LINE},
        }
        yield {"type": "response.completed", "response": {"status": "completed"}}

    async def consume():
        # final_result() claims the stream immediately, so it must run inside the loop.
        parsed = parse_responses_stream(events(), image_segmentation_format())
        return await parsed.final_result()

    result = asyncio.run(consume())
    regions = regions_from_records(result.records, "rectangle")
    assert len(regions) == 1
    assert regions[0].x == 211
    assert regions[0].y == 228
    assert regions[0].w == 60
    assert regions[0].h == 27
    assert regions[0].score == 0.97
    assert regions[0].raster is not None


def test_clamp_box_clips_to_the_image() -> None:
    from dsc_backend.regions import clamp_box

    assert clamp_box(-5, 2, 10, 4, 20, 20) == (0, 2, 5, 4)
    assert clamp_box(15, 15, 10, 10, 20, 20) == (15, 15, 5, 5)
    assert clamp_box(25, 0, 5, 5, 20, 20) is None
