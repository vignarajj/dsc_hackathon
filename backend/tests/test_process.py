import base64
import io
from dataclasses import replace

from fastapi.testclient import TestClient
from PIL import Image

from dsc_backend.config import Settings
from dsc_backend.errors import PipelineError
from dsc_backend.main import create_app
from dsc_backend.regions import Region


class FakeGateway:
    def __init__(
        self, fail_with: Exception | None = None, transcript: str = "Reciept total"
    ) -> None:
        self.fail_with = fail_with
        self.transcript = transcript
        self.concepts: list[str] = []
        self.proofread_calls = 0

    async def segment(self, data_url: str, concept: str) -> list[Region]:
        assert data_url.startswith("data:image/")
        self.concepts.append(concept)
        if self.fail_with is not None and concept == "stamp":
            raise self.fail_with
        if concept != "stamp":
            return []
        return [
            Region(
                x=0,
                y=0,
                w=4,
                h=4,
                label=concept,
                score=0.91,
                raster=b"\x01" * 16,
                mask_width=4,
                mask_height=4,
            )
        ]

    async def transcribe(self, data_url: str) -> str:
        assert data_url.startswith("data:image/")
        return self.transcript

    async def proofread(self, text: str) -> str:
        self.proofread_calls += 1
        assert text == self.transcript
        return "Receipt total"


def _settings(**overrides: object) -> Settings:
    return replace(Settings(meta_api_key="test-key"), **overrides)


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (240, 240, 240)).save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (240, 240, 240)).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_health_and_cors() -> None:
    with TestClient(create_app(_settings(), FakeGateway())) as client:
        health = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert health.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_process_returns_contract_fields() -> None:
    gateway = FakeGateway()
    with TestClient(create_app(_settings(), gateway)) as client:
        response = client.post(
            "/api/process",
            files={"image": ("note.png", _png(), "image/png")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["original_text"] == "Reciept total"
    assert body["cleaned_text"] == "Receipt total"
    assert body["boxes"] == [{"x": 0, "y": 0, "w": 4, "h": 4, "label": "stamp", "score": 0.91}]
    overlay = base64.b64decode(body["overlay_png_base64"])
    assert overlay.startswith(b"\x89PNG")
    assert gateway.concepts == ["stamp", "signature", "photograph", "rectangle"]
    assert gateway.proofread_calls == 1


def test_jpeg_upload_is_accepted() -> None:
    with TestClient(create_app(_settings(), FakeGateway())) as client:
        response = client.post(
            "/api/process",
            files={"image": ("note.jpg", _jpeg(), "image/jpeg")},
        )
    assert response.status_code == 200


def test_empty_transcript_skips_proofread() -> None:
    gateway = FakeGateway(transcript="  ")
    with TestClient(create_app(_settings(), gateway)) as client:
        response = client.post(
            "/api/process",
            files={"image": ("note.png", _png(), "image/png")},
        )
    assert response.status_code == 200
    assert response.json()["original_text"] == ""
    assert response.json()["cleaned_text"] == ""
    assert gateway.proofread_calls == 0


def test_rejects_non_image_and_oversize_upload() -> None:
    app = create_app(_settings(max_upload_bytes=32), FakeGateway())
    with TestClient(app) as client:
        wrong_type = client.post(
            "/api/process",
            files={"image": ("note.gif", b"GIF89a", "image/gif")},
        )
        too_big = client.post(
            "/api/process",
            files={"image": ("note.png", b"x" * 33, "image/png")},
        )
        empty = client.post(
            "/api/process",
            files={"image": ("note.png", b"", "image/png")},
        )
        corrupt = client.post(
            "/api/process",
            files={"image": ("note.png", b"not-a-png", "image/png")},
        )
    assert wrong_type.status_code == 400
    assert wrong_type.json()["detail"] == "Only JPEG and PNG images are accepted"
    assert too_big.status_code == 413
    assert "limit" in too_big.json()["detail"]
    assert empty.status_code == 400
    assert corrupt.status_code == 400


def test_upstream_timeout_is_502() -> None:
    gateway = FakeGateway(fail_with=TimeoutError("slow"))
    with TestClient(create_app(_settings(), gateway)) as client:
        response = client.post(
            "/api/process",
            files={"image": ("note.png", _png(), "image/png")},
        )
    assert response.status_code == 502
    assert response.json()["detail"] == "The model request timed out"


def test_upstream_pipeline_error_is_preserved() -> None:
    gateway = FakeGateway(fail_with=PipelineError(502, "The model request failed"))
    with TestClient(create_app(_settings(), gateway)) as client:
        response = client.post(
            "/api/process",
            files={"image": ("note.png", _png(), "image/png")},
        )
    assert response.status_code == 502
    assert response.json()["detail"] == "The model request failed"
