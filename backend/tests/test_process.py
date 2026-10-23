import base64
import io
from dataclasses import replace

from fastapi.testclient import TestClient
from PIL import Image

from dsc_backend.config import Settings
from dsc_backend.errors import PipelineError
from dsc_backend.main import create_app
from dsc_backend.privacy import Span
from dsc_backend.regions import Region


class FakeGateway:
    def __init__(
        self,
        fail_with: Exception | None = None,
        transcript: str = "Reciept total",
        signatures: list[Region] | Exception | None = None,
    ) -> None:
        self.fail_with = fail_with
        self.transcript = transcript
        self.signature_result = [] if signatures is None else signatures
        self.concepts: list[str] = []
        self.signature_calls: list[tuple[int, int]] = []
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

    async def signatures(self, data_url: str, width: int, height: int) -> list[Region]:
        assert data_url.startswith("data:image/")
        self.signature_calls.append((width, height))
        if isinstance(self.signature_result, Exception):
            raise self.signature_result
        return self.signature_result


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
    assert body["models"] == {
        "segmentation": "sam-3.1",
        "transcription": "muse-spark-1.3",
        "proofread": "muse-spark-1.3",
        "signatures": "muse-spark-1.3",
    }
    assert gateway.signature_calls == [(8, 8)]
    assert body["redacted_png_base64"] is None
    assert body["warnings"] == []


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


def test_omitted_concepts_follow_the_server_default() -> None:
    gateway = FakeGateway()
    settings = _settings(sam_concepts=("signature", "stamp"))
    with TestClient(create_app(settings, gateway)) as client:
        response = client.post(
            "/api/process",
            files={"image": ("note.png", _png(), "image/png")},
        )
    assert response.status_code == 200
    assert gateway.concepts == ["signature", "stamp"]


def test_requested_concepts_limit_which_regions_are_segmented() -> None:
    gateway = FakeGateway()
    with TestClient(create_app(_settings(), gateway)) as client:
        response = client.post(
            "/api/process",
            data={"concepts": " Rectangle, stamp ,STAMP "},
            files={"image": ("note.png", _png(), "image/png")},
        )
    assert response.status_code == 200
    assert gateway.concepts == ["stamp", "rectangle"]
    assert [box["label"] for box in response.json()["boxes"]] == ["stamp"]


def test_empty_concepts_skip_segmentation_and_still_read_text() -> None:
    gateway = FakeGateway()
    with TestClient(create_app(_settings(), gateway)) as client:
        response = client.post(
            "/api/process",
            data={"concepts": " , "},
            files={"image": ("note.png", _png(), "image/png")},
        )
    assert response.status_code == 200
    assert gateway.concepts == []
    assert response.json()["boxes"] == []
    assert response.json()["cleaned_text"] == "Receipt total"


def test_unknown_concept_is_rejected() -> None:
    gateway = FakeGateway()
    with TestClient(create_app(_settings(), gateway)) as client:
        response = client.post(
            "/api/process",
            data={"concepts": "stamp,logo"},
            files={"image": ("note.png", _png(), "image/png")},
        )
    assert response.status_code == 400
    assert "rectangle" in response.json()["detail"]
    assert gateway.concepts == []


def test_upstream_pipeline_error_is_preserved() -> None:
    gateway = FakeGateway(fail_with=PipelineError(502, "The model request failed"))
    with TestClient(create_app(_settings(), gateway)) as client:
        response = client.post(
            "/api/process",
            files={"image": ("note.png", _png(), "image/png")},
        )
    assert response.status_code == 502
    assert response.json()["detail"] == "The model request failed"


class OffImageGateway(FakeGateway):
    async def segment(self, data_url: str, concept: str) -> list[Region]:
        if concept != "stamp":
            return []
        return [
            Region(x=6, y=6, w=10, h=10, label="stamp", score=0.8),
            Region(x=40, y=40, w=4, h=4, label="stamp", score=0.7),
        ]


def test_boxes_are_clipped_and_off_image_boxes_dropped() -> None:
    with TestClient(create_app(_settings(), OffImageGateway())) as client:
        response = client.post(
            "/api/process",
            files={"image": ("note.png", _png(), "image/png")},
        )
    assert response.status_code == 200
    assert response.json()["boxes"] == [
        {"x": 6, "y": 6, "w": 2, "h": 2, "label": "stamp", "score": 0.8}
    ]


def test_rate_limit_returns_429() -> None:
    with TestClient(create_app(_settings(rate_limit_per_minute=1), FakeGateway())) as client:
        first = client.post("/api/process", files={"image": ("note.png", _png(), "image/png")})
        second = client.post("/api/process", files={"image": ("note.png", _png(), "image/png")})
    assert first.status_code == 200
    assert second.status_code == 429
    assert "Too many requests" in second.json()["detail"]


def _signature_at(x: int, y: int, w: int, h: int) -> Region:
    return Region(x=x, y=y, w=w, h=h, label="signature", score=None)


def _post(client: TestClient, **data: str):
    return client.post(
        "/api/process", data=data, files={"image": ("note.png", _png(), "image/png")}
    )


def test_redacted_copy_hides_the_chosen_regions() -> None:
    gateway = FakeGateway(signatures=[_signature_at(4, 4, 4, 4)])
    with TestClient(create_app(_settings(), gateway)) as client:
        response = _post(client, redact="stamp,signature", redact_style="black")
    assert response.status_code == 200
    body = response.json()
    assert body["warnings"] == []
    redacted = Image.open(io.BytesIO(base64.b64decode(body["redacted_png_base64"])))
    assert redacted.format == "PNG"
    assert redacted.getpixel((1, 1)) == (0, 0, 0)
    assert redacted.getpixel((6, 6)) == (0, 0, 0)
    assert body["boxes"][-1] == {
        "x": 4,
        "y": 4,
        "w": 4,
        "h": 4,
        "label": "signature",
        "score": None,
    }


def test_muse_signature_that_repeats_a_sam_one_is_dropped() -> None:
    class SamSignature(FakeGateway):
        async def segment(self, data_url: str, concept: str) -> list[Region]:
            if concept == "signature":
                return [_signature_at(0, 0, 6, 6)]
            return []

    gateway = SamSignature(signatures=[_signature_at(1, 1, 6, 6), _signature_at(6, 6, 2, 2)])
    with TestClient(create_app(_settings(), gateway)) as client:
        response = _post(client)
    signature_boxes = [box for box in response.json()["boxes"] if box["label"] == "signature"]
    assert [(box["x"], box["y"]) for box in signature_boxes] == [(0, 0), (6, 6)]


def test_signature_lookup_failure_is_a_warning_not_an_error() -> None:
    gateway = FakeGateway(signatures=PipelineError(502, "The model request failed"))
    with TestClient(create_app(_settings(), gateway)) as client:
        response = _post(client, redact="signature")
    assert response.status_code == 200
    body = response.json()
    assert body["warnings"] == ["Signatures could not be located, so none are marked or hidden."]
    assert body["redacted_png_base64"]
    assert body["cleaned_text"] == "Receipt total"


def test_hiding_a_region_that_is_not_found_says_so() -> None:
    with TestClient(create_app(_settings(), FakeGateway())) as client:
        response = _post(client, redact="photograph")
    assert response.status_code == 200
    assert response.json()["warnings"] == ["No photograph was found, so none is hidden."]
    assert response.json()["redacted_png_base64"]


def test_signatures_are_not_looked_up_unless_marked() -> None:
    gateway = FakeGateway()
    with TestClient(create_app(_settings(), gateway)) as client:
        _post(client, concepts="stamp")
    assert gateway.signature_calls == []


def test_hidden_regions_must_be_marked_and_the_style_known() -> None:
    gateway = FakeGateway()
    with TestClient(create_app(_settings(), gateway)) as client:
        unmarked = _post(client, concepts="stamp", redact="signature")
        unknown = _post(client, redact="face")
        style = _post(client, redact="stamp", redact_style="pixelate")
    assert unmarked.status_code == 400
    assert "Mark signature" in unmarked.json()["detail"]
    assert unknown.status_code == 400
    assert style.status_code == 400
    assert style.json()["detail"] == "Hidden regions can be black or blur."
    assert gateway.concepts == []


class SensitiveGateway(FakeGateway):
    def __init__(self, spans: list[Span] | Exception, **kwargs: object) -> None:
        super().__init__(transcript="Mr Tom Reed, tel 07911 123456", **kwargs)  # type: ignore[arg-type]
        self.spans = spans
        self.span_calls = 0

    async def proofread(self, text: str) -> str:
        self.proofread_calls += 1
        return "Mr Tom Reed, tel. 07911 123456"

    async def sensitive_spans(self, text: str) -> list[Span]:
        self.span_calls += 1
        assert text == self.transcript
        if isinstance(self.spans, Exception):
            raise self.spans
        return self.spans


def test_sensitive_text_is_masked_in_the_shareable_text() -> None:
    gateway = SensitiveGateway([Span("name", "Tom Reed", "model")])
    with TestClient(create_app(_settings(), gateway)) as client:
        response = _post(client, redact_text="true")
    assert response.status_code == 200
    body = response.json()
    assert body["shareable_text"] == "Mr [NAME], tel. [PHONE]"
    assert body["sensitive"] == [
        {"category": "name", "text": "Tom Reed", "source": "model"},
        {"category": "phone", "text": "07911 123456", "source": "pattern"},
    ]
    assert body["cleaned_text"] == "Mr Tom Reed, tel. 07911 123456"
    assert body["warnings"] == []
    assert body["redacted_png_base64"] is None


def test_model_span_failure_keeps_the_pattern_spans() -> None:
    gateway = SensitiveGateway(PipelineError(502, "The model request failed"))
    with TestClient(create_app(_settings(), gateway)) as client:
        response = _post(client, redact_text="true")
    assert response.status_code == 200
    body = response.json()
    assert body["shareable_text"] == "Mr Tom Reed, tel. [PHONE]"
    assert len(body["warnings"]) == 1
    assert "only phone numbers" in body["warnings"][0]


def test_span_the_proofread_reworded_adds_a_warning() -> None:
    gateway = SensitiveGateway([Span("name", "Mr Tom Reed,", "model")])

    async def reworded(text: str) -> str:
        return "Mister Tom Reed, tel. 07911 123456"

    gateway.proofread = reworded  # type: ignore[method-assign]
    with TestClient(create_app(_settings(), gateway)) as client:
        body = _post(client, redact_text="true").json()
    assert "could not be matched after proofreading" in body["warnings"][0]
    # The surname still stands alone, so it is masked even though the full span moved.
    assert body["shareable_text"] == "Mister Tom [NAME], tel. [PHONE]"


def test_text_is_not_checked_unless_asked() -> None:
    gateway = SensitiveGateway([])
    with TestClient(create_app(_settings(), gateway)) as client:
        body = _post(client).json()
        bad = _post(client, redact_text="maybe")
    assert gateway.span_calls == 0
    assert body["sensitive"] == []
    assert body["shareable_text"] is None
    assert bad.status_code == 400


def test_empty_transcript_gives_empty_shareable_text() -> None:
    gateway = SensitiveGateway([])
    gateway.transcript = " "
    with TestClient(create_app(_settings(), gateway)) as client:
        body = _post(client, redact_text="true").json()
    assert gateway.span_calls == 0
    assert body["shareable_text"] == ""


class TextBoxGateway(SensitiveGateway):
    def __init__(self, boxes: dict[str, list[tuple[int, int, int, int]]] | Exception) -> None:
        super().__init__([Span("name", "Tom Reed", "model")])
        self.boxes = boxes
        self.asked: list[str] = []

    async def text_boxes(
        self, data_url: str, width: int, height: int, lines: list[str]
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        self.asked = lines
        if isinstance(self.boxes, Exception):
            raise self.boxes
        return self.boxes


def test_image_text_is_blacked_out_only_when_the_server_allows_it() -> None:
    gateway = TextBoxGateway({"Tom Reed": [(0, 0, 3, 3)], "07911 123456": [(5, 5, 3, 3)]})
    with TestClient(create_app(_settings(), gateway)) as client:
        off = _post(client, redact_text="true").json()
    assert gateway.asked == []
    assert off["image_text_hidden"] is False
    assert off["redacted_png_base64"] is None
    assert "text_boxes" not in off["models"]

    with TestClient(create_app(_settings(redact_image_text=True), gateway)) as client:
        on = _post(client, redact_text="true").json()
    assert gateway.asked == ["Tom Reed", "07911 123456"]
    assert on["image_text_hidden"] is True
    assert on["models"]["text_boxes"] == "muse-wonder-1.0"
    assert on["warnings"] == []
    image = Image.open(io.BytesIO(base64.b64decode(on["redacted_png_base64"])))
    assert image.getpixel((1, 1)) == (0, 0, 0)
    assert image.getpixel((6, 6)) == (0, 0, 0)
    assert image.getpixel((4, 1)) != (0, 0, 0)


def test_image_text_not_found_or_failing_is_a_warning() -> None:
    partly = TextBoxGateway({"Tom Reed": [(0, 0, 3, 3)]})
    failing = TextBoxGateway(PipelineError(502, "The model request failed"))
    settings = _settings(redact_image_text=True)
    with TestClient(create_app(settings, partly)) as client:
        some = _post(client, redact_text="true").json()
    with TestClient(create_app(settings, failing)) as client:
        none = _post(client, redact_text="true").json()
    assert some["image_text_hidden"] is True
    assert some["warnings"] == [
        "Some sensitive text was not found in the picture, so it is not hidden there."
    ]
    assert none["image_text_hidden"] is False
    assert none["redacted_png_base64"] is None
    assert none["warnings"] == ["Text in the picture could not be located, so it is not hidden."]
    assert none["shareable_text"] == "Mr [NAME], tel. [PHONE]"
