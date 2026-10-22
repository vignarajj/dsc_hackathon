import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dsc_backend.config import Settings, load_settings
from dsc_backend.errors import PipelineError
from dsc_backend.meta import MetaGateway, OpenAIGateway
from dsc_backend.pipeline import ProcessResult, concepts_for_request, process_image
from dsc_backend.ratelimit import RateLimiter

logger = logging.getLogger("dsc")


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
    ) -> ProcessResult:
        settings_for_request: Settings = request.app.state.settings
        client = request.client.host if request.client else "unknown"
        if not request.app.state.limiter.allow(client):
            raise PipelineError(429, "Too many requests. Wait a minute and try again.")
        content_type = image.content_type or ""
        image_bytes = await _read_upload(image, settings_for_request.max_upload_bytes)
        selected = concepts_for_request(concepts, settings_for_request.sam_concepts)
        return await process_image(
            image_bytes,
            content_type,
            request.app.state.gateway,
            settings_for_request,
            selected,
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
