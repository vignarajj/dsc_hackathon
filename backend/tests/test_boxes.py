import pytest

from dsc_backend.boxes import load_json_object, pixel_box
from dsc_backend.errors import PipelineError
from dsc_backend.meta import signature_regions


def test_reads_a_bare_or_fenced_json_object() -> None:
    assert load_json_object('{"a": 1}') == {"a": 1}
    assert load_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert load_json_object('Here you go: {"a": 1} done') == {"a": 1}
    assert load_json_object("no json here") is None
    assert load_json_object("[1, 2]") is None
    assert load_json_object('{"a": }') is None


def test_pixel_box_pads_and_clips() -> None:
    assert pixel_box([10, 10, 30, 20], 100, 100) == (10, 10, 20, 10)
    # 10% of 20 wide is 2 a side; 50% of 10 high is 5 a side.
    assert pixel_box([10, 10, 30, 20], 100, 100, 0.1, 0.5) == (8, 5, 24, 20)
    assert pixel_box([90, 90, 120, 130], 100, 100) == (90, 90, 10, 10)


@pytest.mark.parametrize(
    "value",
    [None, [1, 2, 3], [1, 2, 3, "4"], [30, 10, 10, 20], [10, 20, 30, 20], [True, 0, 5, 5]],
)
def test_pixel_box_rejects_bad_values(value: object) -> None:
    assert pixel_box(value, 100, 100) is None


def test_signature_regions_are_padded_boxes_without_masks() -> None:
    reply = '{"signatures": [{"box": [100, 100, 300, 140]}, {"box": "bad"}]}'
    regions = signature_regions(reply, 1000, 1000)
    assert len(regions) == 1
    region = regions[0]
    assert (region.x, region.y, region.w, region.h) == (70, 70, 260, 100)
    assert region.label == "signature"
    assert region.raster is None


def test_signature_box_over_half_the_page_is_dropped() -> None:
    assert signature_regions('{"signatures": [{"box": [0, 0, 900, 900]}]}', 1000, 1000) == []


def test_empty_list_means_no_signature() -> None:
    assert signature_regions('{"signatures": []}', 1000, 1000) == []


def test_unreadable_signature_reply_is_an_upstream_error() -> None:
    with pytest.raises(PipelineError):
        signature_regions("I see a signature at the bottom.", 1000, 1000)
