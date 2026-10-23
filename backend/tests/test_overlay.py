import io

from PIL import Image

from dsc_backend.imaging import palette, prepare_image, region_colors, render_overlay
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


def test_large_mask_renders_quickly_and_matches_the_raster() -> None:
    import time

    image = Image.new("RGB", (1024, 1024), (255, 255, 255))
    raster = bytes([1, 0]) * (512 * 256)
    region = Region(
        x=0,
        y=0,
        w=1024,
        h=1024,
        label="stamp",
        score=None,
        raster=raster,
        mask_width=512,
        mask_height=512,
    )
    started = time.perf_counter()
    rendered = Image.open(io.BytesIO(render_overlay(image, [region])))
    assert time.perf_counter() - started < 2
    # Even mask columns are on, odd ones off. Each mask pixel covers 2x2 image pixels.
    assert rendered.getpixel((8, 8)) != (255, 255, 255, 255)
    assert rendered.getpixel((10, 8)) == (255, 255, 255, 255)


def test_outline_is_clipped_to_the_image() -> None:
    image = Image.new("RGB", (20, 20), (255, 255, 255))
    region = Region(x=10, y=10, w=50, h=50, label="signature", score=None)
    rendered = Image.open(io.BytesIO(render_overlay(image, [region])))
    assert rendered.size == (20, 20)
    # The right and bottom edges are drawn on the image border, not off it.
    assert rendered.getpixel((19, 15)) != (255, 255, 255, 255)
    assert rendered.getpixel((15, 19)) != (255, 255, 255, 255)


def test_custom_labels_take_the_palette_in_order() -> None:
    colors = region_colors(("stamp", "logo", "qr code", "barcode"))
    assert palette(colors) == {
        "stamp": "#dc2626",
        "logo": "#7c3aed",
        "qr code": "#0d9488",
        "barcode": "#db2777",
    }


def test_overlay_uses_the_color_given_for_a_custom_label() -> None:
    image = Image.new("RGB", (12, 12), (255, 255, 255))
    region = Region(
        x=2,
        y=2,
        w=4,
        h=4,
        label="qr code",
        score=0.9,
        raster=b"\x01" * 16,
        mask_width=4,
        mask_height=4,
    )
    teal = Image.open(
        io.BytesIO(render_overlay(image, [region], region_colors(("logo", "qr code"))))
    )
    purple = Image.open(io.BytesIO(render_overlay(image, [region], region_colors(("qr code",)))))
    teal_pixel, purple_pixel = teal.getpixel((3, 3)), purple.getpixel((3, 3))
    assert isinstance(teal_pixel, tuple) and isinstance(purple_pixel, tuple)
    assert teal_pixel[1] > teal_pixel[0]
    assert purple_pixel[2] > purple_pixel[1]
