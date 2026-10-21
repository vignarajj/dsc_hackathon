import io

from PIL import Image

from dsc_backend.imaging import prepare_image, render_overlay
from dsc_backend.regions import Region


def test_mask_changes_pixels_inside_the_box_only() -> None:
    image = Image.new("RGB", (12, 12), (255, 255, 255))
    region = Region(
        x=2,
        y=2,
        w=4,
        h=4,
        label="stamp",
        score=0.9,
        raster=b"\x01" * 16,
        mask_width=4,
        mask_height=4,
    )
    rendered = Image.open(io.BytesIO(render_overlay(image, [region])))
    assert rendered.format == "PNG"
    assert rendered.getpixel((0, 0)) == (255, 255, 255, 255)
    assert rendered.getpixel((3, 3)) != (255, 255, 255, 255)


def test_long_edge_is_capped_before_the_model_sees_it() -> None:
    source = Image.new("RGB", (3000, 1000), (10, 20, 30))
    buffer = io.BytesIO()
    source.save(buffer, format="PNG")
    prepared = prepare_image(buffer.getvalue(), "image/png", max_edge=2048)
    assert prepared.image.size == (2048, 683)
    assert prepared.data_url.startswith("data:image/")


def test_rectangle_fill_is_lighter_than_a_stamp() -> None:
    image = Image.new("RGB", (12, 12), (255, 255, 255))

    def center(label: str) -> tuple[int, int, int, int]:
        region = Region(
            x=2,
            y=2,
            w=4,
            h=4,
            label=label,
            score=0.9,
            raster=b"\x01" * 16,
            mask_width=4,
            mask_height=4,
        )
        rendered = Image.open(io.BytesIO(render_overlay(image, [region])))
        pixel = rendered.getpixel((3, 3))
        assert isinstance(pixel, tuple)
        return pixel

    stamp = center("stamp")
    rectangle = center("rectangle")
    assert stamp[0] > stamp[1]
    assert rectangle[1] > rectangle[0]
    assert _gap_from_white(rectangle) < _gap_from_white(stamp)


def _gap_from_white(pixel: tuple[int, int, int, int]) -> int:
    return sum(abs(255 - channel) for channel in pixel[:3])


def test_box_without_mask_still_draws_an_outline() -> None:
    image = Image.new("RGB", (12, 12), (255, 255, 255))
    region = Region(x=1, y=1, w=6, h=6, label="signature", score=None)
    rendered = Image.open(io.BytesIO(render_overlay(image, [region])))
    assert rendered.getpixel((1, 1)) != (255, 255, 255, 255)
