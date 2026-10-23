import json

import pytest

from dsc_backend.extraction import InvalidDocument, normalize, parse_document


def _reply(**overrides: object) -> str:
    data: dict[str, object] = {
        "type": "invoice",
        "title": "Invoice INV-2041",
        "summary": "Invoice from Northwind Studio.",
        "fields": [
            {"label": "Invoice number", "value": "INV-2041"},
            {"label": "Total due", "value": "$1,200.00"},
            {"label": "Customer", "value": "Priya Raman"},
        ],
    }
    data.update(overrides)
    return json.dumps(data)


def test_values_are_grounded_ignoring_case_space_and_punctuation() -> None:
    document = parse_document(_reply(), "No. inv 2041\nTotal due: $1200.00")
    assert document.type == "invoice"
    assert [(field.label, field.found_in_text) for field in document.fields] == [
        ("Invoice number", True),
        ("Total due", True),
        ("Customer", False),
    ]


def test_grounding_checks_every_text_given() -> None:
    document = parse_document(_reply(), "Reciept", "Customer Priya Raman")
    assert document.fields[2].found_in_text is True


def test_punctuation_only_value_is_never_grounded() -> None:
    reply = _reply(fields=[{"label": "Mark", "value": "--"}])
    assert parse_document(reply, "-- --").fields[0].found_in_text is False


def test_fields_are_capped_and_overlong_ones_dropped() -> None:
    fields = [{"label": f"Field {n}", "value": str(n)} for n in range(25)]
    fields.insert(0, {"label": "L" * 41, "value": "x"})
    fields.insert(1, {"label": "Long", "value": "v" * 201})
    fields.insert(2, {"label": " ", "value": "x"})
    document = parse_document(_reply(fields=fields), "")
    assert len(document.fields) == 20
    assert document.fields[0].label == "Field 0"


def test_fenced_reply_is_accepted() -> None:
    assert parse_document(f"```json\n{_reply()}\n```", "").title == "Invoice INV-2041"


@pytest.mark.parametrize(
    ("reply", "problem"),
    [
        ("not json", "not a JSON object"),
        (_reply(type="bill"), "type must be one of"),
        (_reply(title=3), "must be strings"),
        (_reply(fields="none"), "must be a list"),
        (_reply(fields=["x"]), "must be an object"),
        (_reply(fields=[{"label": "a", "value": 2}]), "must be a string"),
    ],
)
def test_invalid_replies_say_what_is_wrong(reply: str, problem: str) -> None:
    with pytest.raises(InvalidDocument, match=problem):
        parse_document(reply, "")


def test_normalize_keeps_letters_and_digits_only() -> None:
    assert normalize("  INV-2041, £1 200.00 ") == "inv2041120000"
    assert normalize("Café Müller") == "cafémüller"
