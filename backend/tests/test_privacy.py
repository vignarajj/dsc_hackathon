import pytest

from dsc_backend.errors import PipelineError
from dsc_backend.privacy import (
    CATEGORIES,
    SPANS_FORMAT,
    Span,
    mask_text,
    merge_spans,
    model_spans,
    pattern_spans,
    surnames,
)


def _found(text: str) -> list[tuple[str, str]]:
    return [(span.category, span.text) for span in pattern_spans(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Call +44 113 496 0732 today", [("phone", "+44 113 496 0732")]),
        ("Tel 0161 496 0555", [("phone", "0161 496 0555")]),
        ("ring (020) 7946-0958", [("phone", "(020) 7946-0958")]),
        ("mail d.okafor@mailbox.example now", [("email", "d.okafor@mailbox.example")]),
        ("Account number: 31926819", [("account_number", "31926819")]),
        ("IBAN: GB33BUKB20201555555555", [("account_number", "GB33BUKB20201555555555")]),
        ("IBAN GB33 BUKB 2020 1555 5555 55", [("account_number", "GB33 BUKB 2020 1555 5555 55")]),
        ("card 4111 1111 1111 1111 exp", [("card_number", "4111 1111 1111 1111")]),
        ("Date of birth: 03/07/1991", [("date_of_birth", "03/07/1991")]),
        ("DOB 22 FEB 1988", [("date_of_birth", "22 FEB 1988")]),
        (
            "Account 41003299, sort\ncode 20-32-06.",
            [
                ("account_number", "41003299"),
                ("account_number", "20-32-06"),
            ],
        ),
    ],
)
def test_patterns_find_common_values(text: str, expected: list[tuple[str, str]]) -> None:
    assert _found(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "AUTH 083145 14/10/2026 18:42",
        "Total due: $1,200.00",
        "Ref 60-16-13",
        "Issued 14/10/2026",
        "Notes 12 GBP 480.00",
        "Bristol BS8 1QU",
        "company no. OC398271",
        "INV-2041",
        "4111 1111 1111 1112",  # fails the Luhn check, and too long for a phone
    ],
)
def test_patterns_leave_ordinary_values_alone(text: str) -> None:
    assert _found(text) == []


def test_an_iban_is_not_also_reported_as_digits() -> None:
    assert len(pattern_spans("GB33BUKB20201555555555")) == 1


def test_model_spans_must_be_verbatim_and_use_a_known_category() -> None:
    transcript = "Name: Ana Silva\nPhone 07911 123456\nBananas 1.20"
    reply = (
        '{"items": ['
        '{"category": "name", "text": "Ana Silva"},'
        '{"category": "phone", "text": "07911 123457"},'
        '{"category": "name", "text": "Ana"},'
        '{"category": "name", "text": "Banan"},'
        '{"category": "pet", "text": "Phone"},'
        '{"category": "name", "text": "Ana Silva"},'
        '{"category": "name", "text": " "}'
        "]}"
    )
    spans = model_spans(reply, transcript)
    # "Ana" alone is kept: it is a whole word inside "Ana Silva".
    assert [(span.category, span.text) for span in spans] == [
        ("name", "Ana Silva"),
        ("name", "Ana"),
    ]
    assert all(span.source == "model" for span in spans)


def test_unreadable_model_reply_is_an_upstream_error() -> None:
    with pytest.raises(PipelineError):
        model_spans("Sure! Here are the items.", "text")


def test_merge_prefers_the_model_and_drops_contained_patterns() -> None:
    model = [Span("id_number", "533380006", "model"), Span("address", "Flat 2, 12 Elm Rd", "model")]
    patterns = [
        Span("account_number", "533380006", "pattern"),
        Span("email", "a@b.example", "pattern"),
    ]
    merged = merge_spans(model, patterns)
    assert [(span.category, span.source) for span in merged] == [
        ("id_number", "model"),
        ("address", "model"),
        ("email", "pattern"),
    ]


def test_mask_replaces_every_occurrence_longest_first() -> None:
    text = "Ana Silva wrote. Ana said hi. Bananas cost 2. Call 07911 123456 or 07911 123456."
    spans = [
        Span("name", "Ana", "model"),
        Span("name", "Ana Silva", "model"),
        Span("phone", "07911 123456", "pattern"),
    ]
    assert mask_text(text, spans) == (
        "[NAME] wrote. [NAME] said hi. Bananas cost 2. Call [PHONE] or [PHONE]."
    )


def test_mask_without_spans_returns_the_text() -> None:
    assert mask_text("nothing here", []) == "nothing here"


def test_surnames_of_full_names_are_masked_on_their_own() -> None:
    text = "Mr Thomas Greene\nDear Mr Greene,\nSigned, R. Shah and Ana"
    spans = [
        Span("name", "Thomas Greene", "model"),
        Span("name", "R. Shah", "model"),
        Span("name", "Ana", "model"),
        Span("address", "1 Elm Road", "model"),
    ]
    assert surnames(spans + [Span("name", "Mr Greene", "model")], text) == []
    extra = surnames(spans, text)
    # "Shah" never appears alone, and one-word names have no surname to add.
    assert [(span.category, span.text) for span in extra] == [("name", "Greene")]
    assert mask_text(text, spans + extra) == "Mr [NAME]\nDear Mr [NAME],\nSigned, [NAME] and [NAME]"


def test_the_span_schema_allows_exactly_the_known_categories() -> None:
    item = SPANS_FORMAT["schema"]["properties"]["items"]["items"]  # type: ignore[index]
    assert item["properties"]["category"]["enum"] == list(CATEGORIES)
    assert SPANS_FORMAT["strict"] is True
