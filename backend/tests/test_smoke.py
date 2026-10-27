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
