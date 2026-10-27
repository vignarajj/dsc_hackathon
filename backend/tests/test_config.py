from pathlib import Path

import pytest

from dsc_backend.config import load_settings


def test_missing_api_key_refuses_to_start(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("META_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="META_API_KEY is missing"):
        load_settings(tmp_path / "missing.env")


def test_env_file_supplies_the_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("META_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "META_API_KEY=from-file\nSAM_CONCEPTS=stamp, signature\nCORS_ORIGINS=http://localhost:3000\n",
        encoding="utf-8",
    )
    settings = load_settings(env_file)
    assert settings.meta_api_key == "from-file"
    assert settings.sam_concepts == ("stamp", "signature")
    assert settings.cors_origins == ("http://localhost:3000",)
    assert settings.sam_model == "sam-3.1"
    assert settings.upstream_timeout_seconds == 60.0


def test_image_text_redaction_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.delenv("REDACT_IMAGE_TEXT", raising=False)
    assert load_settings(tmp_path / "none.env").redact_image_text is False
    monkeypatch.setenv("REDACT_IMAGE_TEXT", "true")
    assert load_settings(tmp_path / "none.env").redact_image_text is True
    monkeypatch.setenv("REDACT_IMAGE_TEXT", "sometimes")
    with pytest.raises(RuntimeError):
        load_settings(tmp_path / "none.env")


def test_request_budget_setting(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.delenv("REQUEST_BUDGET_SECONDS", raising=False)
    assert load_settings(tmp_path / "none.env").request_budget_seconds == 150.0
    monkeypatch.setenv("REQUEST_BUDGET_SECONDS", "90")
    assert load_settings(tmp_path / "none.env").request_budget_seconds == 90.0
    monkeypatch.setenv("REQUEST_BUDGET_SECONDS", "0")
    with pytest.raises(RuntimeError, match="positive"):
        load_settings(tmp_path / "none.env")
