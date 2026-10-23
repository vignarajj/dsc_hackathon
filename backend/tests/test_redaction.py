import io

from PIL import Image

from dsc_backend.redaction import hide_mask, render_redacted
from dsc_backend.regions import Region

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


def _half_mask_region(label: str = "signature") -> Region:
    # A 40x40 box whose mask covers the left half only.
    row = b"\x01" * 20 + b"\x00" * 20
    return Region(
        x=20,
        y=20,
        w=40,
        h=40,
        label=label,
        score=0.9,
        raster=row * 40,
        mask_width=40,
        mask_height=40,
    )


def _open(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png))


def test_black_fill_follows_the_mask_not_the_box() -> None:
    image = Image.new("RGB", (80, 80), WHITE)
    png, hidden = render_redacted(image, [_half_mask_region()], {"signature"}, "black")
    out = _open(png)
    assert hidden == 1
    assert out.getpixel((25, 40)) == BLACK
    # The right half of the box is outside the mask, beyond the dilation.
    assert out.getpixel((55, 40)) == WHITE
    assert out.getpixel((5, 5)) == WHITE


def test_dilation_covers_the_mask_edge() -> None:
    image = Image.new("RGB", (80, 80), WHITE)
    out = _open(render_redacted(image, [_half_mask_region()], {"signature"}, "black")[0])
    # Columns 20-39 are the mask. Three pixels either side are hidden too.
    assert out.getpixel((17, 40)) == BLACK
    assert out.getpixel((42, 40)) == BLACK
    assert out.getpixel((16, 40)) == WHITE
    assert out.getpixel((43, 40)) == WHITE


def test_region_without_a_mask_hides_its_whole_box() -> None:
    image = Image.new("RGB", (80, 80), WHITE)
    region = Region(x=10, y=10, w=30, h=20, label="signature", score=None)
    out = _open(render_redacted(image, [region], {"signature"}, "black")[0])
    assert out.getpixel((10, 10)) == BLACK
    assert out.getpixel((39, 29)) == BLACK
    assert out.getpixel((50, 50)) == WHITE


def test_only_the_chosen_labels_are_hidden() -> None:
    image = Image.new("RGB", (80, 80), WHITE)
    stamp = Region(x=0, y=0, w=10, h=10, label="stamp", score=None)
    out_png, hidden = render_redacted(image, [stamp, _half_mask_region()], {"signature"}, "black")
    out = _open(out_png)
    assert hidden == 1
    assert out.getpixel((2, 2)) == WHITE


def test_box_partly_off_the_image_is_clipped() -> None:
    image = Image.new("RGB", (40, 40), WHITE)
    region = Region(x=30, y=30, w=50, h=50, label="stamp", score=None)
    out = _open(render_redacted(image, [region], {"stamp"}, "black")[0])
    assert out.size == (40, 40)
    assert out.getpixel((39, 39)) == BLACK
    assert out.getpixel((10, 10)) == WHITE


def test_blur_changes_pixels_inside_the_mask_only() -> None:
    image = Image.new("RGB", (120, 120), WHITE)
    for x in range(0, 120, 2):
        for y in range(120):
            image.putpixel((x, y), BLACK)
    region = Region(x=40, y=40, w=40, h=40, label="photograph", score=None)
    out = _open(render_redacted(image, [region], {"photograph"}, "blur")[0])
    inside = out.getpixel((60, 60))
    assert inside not in (BLACK, WHITE)
    mask, _ = hide_mask(image.size, [region], {"photograph"})
    for point in [(0, 0), (30, 30), (100, 60), (60, 100), (36, 60)]:
        assert mask.getpixel(point) == 0
        assert out.getpixel(point) == image.getpixel(point)


def test_output_has_no_metadata() -> None:
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[0x8825] = {2: (51.0, 30.0, 0.0)}  # GPS latitude
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), WHITE).save(buffer, format="JPEG", exif=exif)
    source = Image.open(io.BytesIO(buffer.getvalue()))
    source.load()
    assert source.getexif()

    out = _open(render_redacted(source, [], {"signature"}, "black")[0])
    assert out.format == "PNG"
    assert not out.getexif()
    assert "exif" not in out.info


def test_text_boxes_are_black_even_when_the_style_is_blur() -> None:
    image = Image.new("RGB", (60, 60), WHITE)
    out = _open(render_redacted(image, [], set(), "blur", text_boxes=[(5, 5, 10, 4)])[0])
    assert out.getpixel((5, 5)) == BLACK
    assert out.getpixel((14, 8)) == BLACK
    assert out.getpixel((20, 20)) == WHITE
