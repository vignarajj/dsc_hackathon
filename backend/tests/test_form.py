import pytest

from dsc_backend.errors import PipelineError
from dsc_backend.form import custom_concepts_for_request, redaction_for_request

PRESETS = ("stamp", "signature")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, PRESETS),
        ("", PRESETS),
        ("logo", (*PRESETS, "logo")),
        ("  QR   Code , logo,qr code", (*PRESETS, "qr code", "logo")),
        ("t-shirt", (*PRESETS, "t-shirt")),
        ("Stamp", PRESETS),
        ("photo", ("stamp", "signature", "photograph")),
        ("rectangle, logo", ("stamp", "signature", "rectangle", "logo")),
        ("logo, qr code, barcode, stamp", (*PRESETS, "logo", "qr code", "barcode")),
    ],
)
def test_custom_names_are_normalized_and_follow_the_presets(
    raw: str | None, expected: tuple[str, ...]
) -> None:
    assert custom_concepts_for_request(raw, PRESETS) == expected


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("company logo mark here", "1 to 3 plain words"),
        ("qr code 2", "1 to 3 plain words"),
        ("a" * 31, "1 to 3 plain words"),
        ("logo 🙂", "1 to 3 plain words"),
        ("-logo", "1 to 3 plain words"),
        ("Printed Text", "not text"),
        ("handwriting", "not text"),
        ("logo, qr code, barcode, face", "up to 3"),
    ],
)
def test_bad_custom_names_are_rejected(raw: str, message: str) -> None:
    with pytest.raises(PipelineError) as caught:
        custom_concepts_for_request(raw, PRESETS)
    assert caught.value.status_code == 400
    assert message in caught.value.message


def test_seven_sam_calls_at_most() -> None:
    every = ("stamp", "signature", "photograph", "rectangle")
    assert len(custom_concepts_for_request("logo, qr code, barcode", every)) == 7


def test_custom_regions_can_be_hidden_once_marked() -> None:
    concepts = ("signature", "logo", "qr code")
    hide = redaction_for_request(" QR code ,Logo", None, concepts)
    assert hide.labels == ("logo", "qr code")
    with pytest.raises(PipelineError, match="Mark face"):
        redaction_for_request("face", None, concepts)
