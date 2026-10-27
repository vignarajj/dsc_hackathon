import pytest
from fastapi.testclient import TestClient

from dsc_backend.config import load_settings
from dsc_backend.main import create_app
from dsc_backend.privacy import Span
from test_process import (
    INVOICE_JSON,
    DescribeGateway,
    ExtractGateway,
    SensitiveGateway,
    _post,
    _settings,
)
from test_stream import STREAM, _events
from test_stream import _post as _stream_post


def test_config_reports_the_features_this_server_runs() -> None:
    settings = _settings(feature_extract=False, redact_image_text=True)
    with TestClient(create_app(settings, DescribeGateway())) as client:
        body = client.get("/api/config").json()
    assert body == {
        "features": {"extract": False, "describe": True, "privacy": True, "image_text": True}
    }


def test_extraction_turned_off_makes_no_call_and_says_so() -> None:
    gateway = ExtractGateway([INVOICE_JSON])
    with TestClient(create_app(_settings(feature_extract=False), gateway)) as client:
        body = _post(client, extract="true").json()
        events = _events(_stream_post(client, STREAM, extract="true"))
    assert gateway.extract_calls == []
    assert body["document"] is None
    assert body["warnings"] == ["Key fields are turned off on this server."]
    assert "extraction" not in body["models"]
    assert "extract" not in events[0]["stages"]  # type: ignore[operator]


def test_descriptions_turned_off_make_no_call_and_say_so() -> None:
    gateway = DescribeGateway()
    with TestClient(create_app(_settings(feature_describe=False), gateway)) as client:
        body = _post(client, describe="true").json()
    assert gateway.described == 0
    assert body["boxes"][0]["description"] is None
    assert body["warnings"] == ["Region descriptions are turned off on this server."]


def test_privacy_turned_off_keeps_the_free_patterns() -> None:
    gateway = SensitiveGateway([Span("name", "Tom Reed", "model")])
    with TestClient(create_app(_settings(feature_privacy=False), gateway)) as client:
        body = _post(client, redact_text="true").json()
    assert gateway.span_calls == 0
    assert body["shareable_text"] == "Mr Tom Reed, tel. [PHONE]"
    assert len(body["warnings"]) == 1
    assert "turned off on this server" in body["warnings"][0]


def test_features_left_alone_when_not_asked_for() -> None:
    gateway = ExtractGateway([INVOICE_JSON])
    with TestClient(create_app(_settings(feature_extract=False), gateway)) as client:
        body = _post(client).json()
    assert body["warnings"] == []


@pytest.mark.parametrize("name", ["FEATURE_EXTRACT", "FEATURE_DESCRIBE", "FEATURE_PRIVACY"])
def test_feature_flags_default_on_and_read_false(
    name: str, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("META_API_KEY", "k")
    field = name.lower()
    monkeypatch.delenv(name, raising=False)
    assert getattr(load_settings(tmp_path / "none.env"), field) is True
    monkeypatch.setenv(name, "false")
    assert getattr(load_settings(tmp_path / "none.env"), field) is False
    monkeypatch.setenv(name, "maybe")
    with pytest.raises(RuntimeError, match="true or false"):
        load_settings(tmp_path / "none.env")
