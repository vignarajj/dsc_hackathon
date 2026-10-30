import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dsc_backend.config import Settings
from dsc_backend.main import create_app
from fake_server import FakeGateway

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke.py"
spec = importlib.util.spec_from_file_location("smoke", SCRIPT)
assert spec is not None and spec.loader is not None
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.fixture
def client():
    with TestClient(create_app(Settings(meta_api_key="unused"), FakeGateway())) as test_client:
        yield test_client


def test_a_sample_runs_end_to_end_and_each_check_is_reported(client: TestClient) -> None:
    rows = smoke.run(client, [smoke.SAMPLES / "signed-form.jpg"], ask=True)
    [row] = rows
    # The fake gateway's form has two values that appear in its text, so the
    # "3 grounded fields" check fails, and only that one.
    assert row.problems == ["2 grounded fields, expected 3 or more"]
    assert "type=form" in row.summary
    assert "signature: 1" in row.summary
    assert "It is Daniel Okafor's form." in row.summary


def test_a_wrong_document_type_fails(client: TestClient) -> None:
    [row] = smoke.run(client, [smoke.SAMPLES / "invoice.jpg"])
    assert "type 'form', expected 'invoice'" in row.problems


def test_pages_without_expectations_get_the_general_checks(
    client: TestClient, tmp_path: Path
) -> None:
    page = tmp_path / "mine.jpg"
    page.write_bytes((smoke.SAMPLES / "chat.jpg").read_bytes())
    [row] = smoke.run(client, [page])
    assert row.passed


def test_an_error_status_is_a_failure(client: TestClient, tmp_path: Path) -> None:
    page = tmp_path / "broken.png"
    page.write_bytes(b"not an image")
    [row] = smoke.run(client, [page])
    assert row.problems == ["HTTP 400: Upload is not a valid JPEG or PNG image"]
    assert "FAIL" in smoke.table([row])


def test_nothing_is_sent_without_yes(capsys: pytest.CaptureFixture[str]) -> None:
    assert smoke.main(["--base-url", "http://127.0.0.1:9"]) == 1
    out = capsys.readouterr().out
    assert "about 36 model calls" in out
    assert "Nothing sent" in out


def test_the_estimate_counts_descriptions_and_questions(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    page = tmp_path / "mine.jpg"
    page.write_bytes(b"x")
    assert smoke.main(["--describe", "--ask", str(page)]) == 1
    assert "up to 18 model calls" in capsys.readouterr().out


def test_describe_sends_the_field_and_checks_each_region_has_a_description(
    client: TestClient, tmp_path: Path
) -> None:
    page = tmp_path / "mine.jpg"
    page.write_bytes((smoke.SAMPLES / "signed-form.jpg").read_bytes())
    [row] = smoke.run(client, [page], describe=True)
    assert row.passed, row.problems


def test_describe_fails_when_the_server_has_descriptions_off(tmp_path: Path) -> None:
    page = tmp_path / "mine.jpg"
    page.write_bytes((smoke.SAMPLES / "signed-form.jpg").read_bytes())
    off = Settings(meta_api_key="unused", feature_describe=False)
    with TestClient(create_app(off, FakeGateway())) as client:
        [row] = smoke.run(client, [page], describe=True)
    assert any("no region descriptions" in problem for problem in row.problems)


def test_delay_waits_before_every_request_after_the_first(client: TestClient) -> None:
    waits: list[float] = []
    smoke.run(
        client,
        [smoke.SAMPLES / "chat.jpg", smoke.SAMPLES / "invoice.jpg"],
        ask=True,
        delay=13,
        sleep=waits.append,
    )
    # Four requests (two pages, two questions): three waits, none before the first.
    assert waits == [13, 13, 13]


def test_a_rate_limited_page_says_how_to_slow_down() -> None:
    limited = Settings(meta_api_key="unused", rate_limit_per_minute=1)
    with TestClient(create_app(limited, FakeGateway())) as client:
        rows = smoke.run(client, [smoke.SAMPLES / "chat.jpg", smoke.SAMPLES / "invoice.jpg"])
    assert "HTTP 429" in rows[1].problems[0]
    assert "--delay 13" in rows[1].problems[0]


def test_a_receipt_photo_is_checked_for_its_type(client: TestClient, tmp_path: Path) -> None:
    page = tmp_path / "receipt.jpg"
    page.write_bytes((smoke.SAMPLES / "chat.jpg").read_bytes())
    [row] = smoke.run(client, [page])
    assert "type 'form', expected 'receipt'" in row.problems
