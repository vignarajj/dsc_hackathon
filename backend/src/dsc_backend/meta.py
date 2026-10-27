import logging
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import aclosing
from typing import Protocol

from meta_sam_parser import image_segmentation_format, parse_responses_stream
from openai import APITimeoutError, AsyncOpenAI

from dsc_backend.ask import ASK_FORMAT, Question
from dsc_backend.boxes import load_json_object, pixel_box
from dsc_backend.config import Settings
from dsc_backend.errors import PipelineError
from dsc_backend.extraction import EXTRACT_FORMAT
from dsc_backend.privacy import SPANS_FORMAT, Span, model_spans
from dsc_backend.prompts import (
    DESCRIBE_PROMPT,
    TRANSCRIBE_PROMPT,
    ask_prompt,
    extract_prompt,
    proofread_prompt,
    sam_prompt,
    signature_prompt,
    spans_prompt,
    strip_transcript_tags,
    text_box_prompt,
)
from dsc_backend.regions import Region
from dsc_backend.sam import ensure_completed, regions_from_records

logger = logging.getLogger(__name__)

# Margin as a share of the box. Muse boxes are often a little short; this
# covered every signature in the spike.
_SIGNATURE_PAD_X = 0.15
_SIGNATURE_PAD_Y = 0.75
_MAX_SIGNATURES = 10
# In the F0 spike this margin made muse-wonder-1.0 boxes cover 24 of 24 words.
_TEXT_PAD_X = 0.2
_TEXT_PAD_Y = 0.75
_MAX_TEXT_LINES = 20


class MetaGateway(Protocol):
    async def segment(self, data_url: str, concept: str) -> list[Region]: ...

    async def transcribe(self, data_url: str) -> str: ...

    async def proofread(self, text: str) -> str: ...

    async def signatures(self, data_url: str, width: int, height: int) -> list[Region]: ...

    async def sensitive_spans(self, text: str) -> list[Span]: ...

    async def extract(self, text: str, problem: str | None = None) -> str: ...

    async def describe_region(self, data_url: str) -> str: ...

    async def ask(self, question: Question) -> str: ...

    async def text_boxes(
        self, data_url: str, width: int, height: int, lines: list[str]
    ) -> dict[str, list[tuple[int, int, int, int]]]: ...


class OpenAIGateway:
    """Meta Model API client. SAM must be streamed; Muse calls are not."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.meta_api_key,
            base_url=settings.meta_base_url,
            timeout=settings.upstream_timeout_seconds,
            max_retries=0,
        )

    async def aclose(self) -> None:
        await self._client.close()

    async def segment(self, data_url: str, concept: str) -> list[Region]:
        try:
            stream = await self._client.responses.create(
                model=self._settings.sam_model,
                stream=True,
                metadata={"mask_encoding": "one_bit", "include_confidence": "true"},
                input=[
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": sam_prompt(concept)},
                            {"type": "input_image", "image_url": data_url},
                        ],
                    }
                ],
                timeout=self._settings.upstream_timeout_seconds,
            )
            # Close the event generator before the HTTP stream. The parser is
            # still suspended on the body when it returns, and an implicit
            # aclose() of a running generator fails.
            async with stream, aclosing(_event_dicts(stream)) as events:
                result = await parse_responses_stream(
                    events,
                    image_segmentation_format(),
                ).final_result()
        except PipelineError:
            raise
        except Exception as exc:
            raise _upstream_error(exc) from exc
        records = ensure_completed(result, concept)
        return regions_from_records(records, concept)

    async def transcribe(self, data_url: str) -> str:
        return await self._text_response(
            self._settings.muse_vision_model,
            [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": TRANSCRIBE_PROMPT},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
        )

    async def proofread(self, text: str) -> str:
        cleaned = await self._text_response(
            self._settings.muse_text_model,
            [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": proofread_prompt(text)},
                    ],
                }
            ],
        )
        return strip_transcript_tags(cleaned)

    async def signatures(self, data_url: str, width: int, height: int) -> list[Region]:
        reply = await self._text_response(
            self._settings.muse_signature_model,
            [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": signature_prompt(width, height)},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
        )
        return signature_regions(reply, width, height)

    async def sensitive_spans(self, text: str) -> list[Span]:
        reply = await self._text_response(
            self._settings.muse_text_model,
            [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": spans_prompt(text)},
                    ],
                }
            ],
            text_format=SPANS_FORMAT,
        )
        return model_spans(reply, text)

    async def text_boxes(
        self, data_url: str, width: int, height: int, lines: list[str]
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        asked = lines[:_MAX_TEXT_LINES]
        prompt = text_box_prompt(width, height, asked)
        reply = await self._text_response(
            self._settings.muse_text_box_model,
            [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
        )
        return text_regions(reply, width, height, asked)

    async def extract(self, text: str, problem: str | None = None) -> str:
        """Ask for the document as JSON. problem, when set, says what was wrong last time."""
        return await self._text_response(
            self._settings.muse_text_model,
            [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": extract_prompt(text, problem)},
                    ],
                }
            ],
            text_format=EXTRACT_FORMAT,
        )

    async def describe_region(self, data_url: str) -> str:
        return await self._text_response(
            self._settings.muse_vision_model,
            [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": DESCRIBE_PROMPT},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
        )

    async def ask(self, question: Question) -> str:
        return await self._text_response(
            self._settings.muse_text_model,
            [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": ask_prompt(question)}],
                }
            ],
            text_format=ASK_FORMAT,
        )

    async def _text_response(
        self,
        model: str,
        payload: list[dict[str, object]],
        text_format: dict[str, object] | None = None,
    ) -> str:
        # Strict JSON schema output held for every run in the F0 spike.
        extra: dict[str, object] = {"text": {"format": text_format}} if text_format else {}
        try:
            response = await self._client.responses.create(
                model=model,
                input=payload,
                timeout=self._settings.upstream_timeout_seconds,
                **extra,
            )
        except Exception as exc:
            raise _upstream_error(exc) from exc
        return (getattr(response, "output_text", None) or "").strip()


def signature_regions(reply: str, width: int, height: int) -> list[Region]:
    """Read Muse's signature boxes. An unreadable reply is an upstream failure."""
    data = load_json_object(reply)
    items = data.get("signatures") if data is not None else None
    if not isinstance(items, list):
        raise PipelineError(502, "The model request failed")
    regions: list[Region] = []
    for item in items[:_MAX_SIGNATURES]:
        box = pixel_box(
            item.get("box") if isinstance(item, dict) else None,
            width,
            height,
            _SIGNATURE_PAD_X,
            _SIGNATURE_PAD_Y,
        )
        if box is None:
            continue
        x, y, w, h = box
        # A box over half the page is the model naming the whole document.
        if w * h > width * height // 2:
            continue
        regions.append(Region(x=x, y=y, w=w, h=h, label="signature", score=None))
    return regions


def text_regions(
    reply: str, width: int, height: int, lines: list[str]
) -> dict[str, list[tuple[int, int, int, int]]]:
    """Read Muse's word boxes, keeping only boxes for the strings that were asked."""
    data = load_json_object(reply)
    items = data.get("boxes") if data is not None else None
    if not isinstance(items, list):
        raise PipelineError(502, "The model request failed")
    found: dict[str, list[tuple[int, int, int, int]]] = {}
    for item in items:
        if not isinstance(item, dict) or item.get("text") not in lines:
            continue
        box = pixel_box(item.get("box"), width, height, _TEXT_PAD_X, _TEXT_PAD_Y)
        # A word box over a quarter of the image is not a word.
        if box is None or box[2] * box[3] > width * height // 4:
            continue
        found.setdefault(str(item["text"]), []).append(box)
    return found


async def _event_dicts(stream: AsyncIterable[object]) -> AsyncIterator[dict[str, object]]:
    async for event in stream:
        if isinstance(event, dict):
            yield event
            continue
        dump = getattr(event, "model_dump", None)
        if dump is None:
            raise PipelineError(502, "The model request failed")
        data = dump()
        if not isinstance(data, dict):
            raise PipelineError(502, "The model request failed")
        yield data


def _upstream_error(exc: Exception) -> PipelineError:
    if isinstance(exc, PipelineError):
        return exc
    if isinstance(exc, APITimeoutError | TimeoutError):
        logger.warning("upstream timeout: %s", type(exc).__name__)
        return PipelineError(502, "The model request timed out")
    logger.warning("upstream failure: %s", type(exc).__name__)
    return PipelineError(502, "The model request failed")
