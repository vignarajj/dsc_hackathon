import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from dsc_backend.config import Settings, load_settings
from dsc_backend.errors import PipelineError
from dsc_backend.form import (
    concepts_for_request,
    custom_concepts_for_request,
    flag_for_request,
    redaction_for_request,
)
from dsc_backend.imaging import prepare_image
from dsc_backend.meta import MetaGateway, OpenAIGateway
from dsc_backend.pipeline import ProcessResult, process_image
from dsc_backend.progress import Emit, ndjson_stream
from dsc_backend.ratelimit import RateLimiter

logger = logging.getLogger("dsc")


class SpanModel(BaseModel):
    category: str
    text: str
    source: str


class FieldModel(BaseModel):
    label: str
    value: str
    found_in_text: bool


class DocumentModel(BaseModel):
    type: str
    title: str
    summary: str
    fields: list[FieldModel]


class BoxModel(BaseModel):
    x: int
    y: int
    w: int
    h: int
    label: str
    score: float | None


class ProcessResponse(BaseModel):
    boxes: list[BoxModel]
    overlay_png_base64: str
    original_text: str
    cleaned_text: str
    models: dict[str, str]
    palette: dict[str, str]
    redacted_png_base64: str | None
    sensitive: list[SpanModel]
    shareable_text: str | None
    image_text_hidden: bool
    document: DocumentModel | None
    warnings: list[str]


def create_app(
    settings: Settings | None = None,
    gateway: MetaGateway | None = None,
) -> FastAPI:
    resolved = settings if settings is not None else load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owns_gateway = app.state.gateway is None
        if owns_gateway:
            app.state.gateway = OpenAIGateway(app.state.settings)
        try:
            yield
        finally:
            if owns_gateway:
                await app.state.gateway.aclose()

    app = FastAPI(title="Document Screenshot Cleaner", lifespan=lifespan)
    app.state.settings = resolved
    app.state.gateway = gateway
    app.state.limiter = RateLimiter(resolved.rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.add_exception_handler(PipelineError, _pipeline_error)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/process", response_model=ProcessResponse)
    async def process(
        request: Request,
        image: UploadFile = File(...),
        concepts: str | None = Form(default=None),
        custom: str | None = Form(default=None),
        redact: str | None = Form(default=None),
        redact_style: str | None = Form(default=None),
        redact_text: str | None = Form(default=None),
        extract: str | None = Form(default=None),
    ) -> ProcessResult | StreamingResponse:
        settings_for_request: Settings = request.app.state.settings
        client = request.client.host if request.client else "unknown"
        if not request.app.state.limiter.allow(client):
            raise PipelineError(429, "Too many requests. Wait a minute and try again.")
        content_type = image.content_type or ""
        image_bytes = await _read_upload(image, settings_for_request.max_upload_bytes)
        selected = custom_concepts_for_request(
            custom, concepts_for_request(concepts, settings_for_request.sam_concepts)
        )
        redaction = redaction_for_request(redact, redact_style, selected, redact_text)
        wants_document = flag_for_request(extract, "extract")
        # Decode before any streaming starts, so a bad upload is still a plain 400.
        prepared = prepare_image(image_bytes, content_type, settings_for_request.max_image_edge)
        gateway_for_request: MetaGateway = request.app.state.gateway

        async def run(emit: Emit | None = None) -> ProcessResult:
            return await process_image(
                prepared,
                gateway_for_request,
                settings_for_request,
                selected,
                redaction,
                wants_document,
                emit,
            )

        if "application/x-ndjson" not in request.headers.get("accept", ""):
            return await run()

        async def work(emit: Emit) -> dict[str, object]:
            result = await run(emit)
            return ProcessResponse.model_validate(result, from_attributes=True).model_dump()

        return StreamingResponse(
            ndjson_stream(work),
            media_type="application/x-ndjson",
            # Ask proxies not to buffer, so each stage reaches the page as it happens.
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


async def _pipeline_error(_request: Request, exc: Exception) -> JSONResponse:
    error = (
        exc if isinstance(exc, PipelineError) else PipelineError(502, "The model request failed")
    )
    return JSONResponse(status_code=error.status_code, content={"detail": error.message})


async def _read_upload(upload: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise PipelineError(413, _limit_message(limit))
        chunks.append(chunk)
    if size == 0:
        raise PipelineError(400, "Image file is empty")
    return b"".join(chunks)


def _limit_message(limit: int) -> str:
    megabyte = 1024 * 1024
    if limit % megabyte == 0:
        return f"Image exceeds the {limit // megabyte} MB limit"
    return f"Image exceeds the {limit} byte limit"


def _build_default_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        return create_app()
    except RuntimeError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc


app = _build_default_app()
