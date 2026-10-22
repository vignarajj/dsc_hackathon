import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
DEFAULT_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
DEFAULT_CONCEPTS = ("stamp", "signature", "photograph", "rectangle")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class Settings:
    meta_api_key: str
    meta_base_url: str = "https://api.meta.ai/v1"
    sam_model: str = "sam-3.1"
    muse_vision_model: str = "muse-spark-1.3"
    muse_text_model: str = "muse-spark-1.3"
    cors_origins: tuple[str, ...] = DEFAULT_ORIGINS
    sam_concepts: tuple[str, ...] = DEFAULT_CONCEPTS
    max_upload_bytes: int = MAX_UPLOAD_BYTES
    upstream_timeout_seconds: float = 60.0
    max_image_edge: int = 2048
    rate_limit_per_minute: int = 0


def load_settings(env_file: Path | None = None) -> Settings:
    """Load runtime settings. Missing META_API_KEY is fatal."""
    path = DEFAULT_ENV_FILE if env_file is None else env_file
    if path.is_file():
        load_dotenv(path, override=False)

    key = os.environ.get("META_API_KEY", "").strip()
    if not key:
        raise RuntimeError("META_API_KEY is missing. Add it to backend/.env and restart.")

    return Settings(
        meta_api_key=key,
        meta_base_url=_text("META_BASE_URL", "https://api.meta.ai/v1"),
        sam_model=_text("SAM_MODEL", "sam-3.1"),
        muse_vision_model=_text("MUSE_VISION_MODEL", "muse-spark-1.3"),
        muse_text_model=_text("MUSE_TEXT_MODEL", "muse-spark-1.3"),
        cors_origins=_csv("CORS_ORIGINS", DEFAULT_ORIGINS),
        sam_concepts=_csv("SAM_CONCEPTS", DEFAULT_CONCEPTS),
        max_upload_bytes=MAX_UPLOAD_BYTES,
        upstream_timeout_seconds=_positive_float("UPSTREAM_TIMEOUT_SECONDS", 60.0),
        max_image_edge=2048,
        rate_limit_per_minute=_non_negative_int("RATE_LIMIT_PER_MINUTE", 0),
    )


def _text(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    items = tuple(part.strip() for part in raw.split(",") if part.strip())
    return items or default


def _positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be positive")
    return value


def _non_negative_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a whole number") from exc
    if value < 0:
        raise RuntimeError(f"{name} must be zero or more")
    return value
