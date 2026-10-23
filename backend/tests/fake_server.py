"""Run the API with a fake model gateway, for the browser tests. Never calls Meta.

uv run python tests/fake_server.py [port]
"""

import asyncio
import base64
import io
import json
import os
import sys

from PIL import Image

os.environ.setdefault("META_API_KEY", "fake-key-for-browser-tests")

import uvicorn  # noqa: E402

from dsc_backend.ask import NOT_IN_DOCUMENT, Question  # noqa: E402
from dsc_backend.config import Settings  # noqa: E402
from dsc_backend.main import create_app  # noqa: E402
from dsc_backend.privacy import Span  # noqa: E402
from dsc_backend.regions import Region  # noqa: E402

TRANSCRIPT = (
    "Membership Application Form\n"
    "Full name: Daniel Okafor\n"
    "Phone: 07700 900461\n"
    "Email: d.okafor@mailbox.example\n"
    "Signture of applicant"
)
# Where each region sits, as shares of the image: left, top, width, height.
PLACES = {
    "stamp": (0.62, 0.62, 0.18, 0.14),
    "photograph": (0.66, 0.06, 0.2, 0.2),
    "signature": (0.08, 0.66, 0.3, 0.08),
    "logo": (0.08, 0.06, 0.2, 0.06),
    "qr code": (0.7, 0.4, 0.15, 0.12),
}


def _size(data_url: str) -> tuple[int, int]:
    payload = base64.b64decode(data_url.split(",", 1)[1])
    return Image.open(io.BytesIO(payload)).size


def _region(label: str, width: int, height: int, masked: bool) -> Region:
    left, top, w_share, h_share = PLACES[label]
    x, y, w, h = (
        round(left * width),
        round(top * height),
        round(w_share * width),
        round(h_share * height),
    )
    if not masked:
        return Region(x, y, w, h, label, None)
    # A round mask, so the overlay and the share-safe copy follow a real shape.
    raster = bytes(
        1 if (col - w / 2) ** 2 / (w / 2) ** 2 + (row - h / 2) ** 2 / (h / 2) ** 2 <= 1 else 0
        for row in range(h)
        for col in range(w)
    )
    return Region(x, y, w, h, label, 0.9, raster, w, h)


class FakeGateway:
    async def segment(self, data_url: str, concept: str) -> list[Region]:
        if concept not in PLACES or concept == "signature":
            return []
        return [_region(concept, *_size(data_url), masked=True)]

    async def transcribe(self, data_url: str) -> str:
        return TRANSCRIPT

    async def proofread(self, text: str) -> str:
        # A pause, so the browser tests can see a stage in progress.
        await asyncio.sleep(float(os.environ.get("FAKE_DELAY_SECONDS", "0")))
        return text.replace("Signture", "Signature")

    async def signatures(self, data_url: str, width: int, height: int) -> list[Region]:
        return [_region("signature", width, height, masked=False)]

    async def sensitive_spans(self, text: str) -> list[Span]:
        return [Span("name", "Daniel Okafor", "model")]

    async def text_boxes(
        self, data_url: str, width: int, height: int, lines: list[str]
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        return {}

    async def extract(self, text: str, problem: str | None = None) -> str:
        return json.dumps(
            {
                "type": "form",
                "title": "Membership application",
                "summary": "A library membership form for Daniel Okafor.",
                "fields": [
                    {"label": "Full name", "value": "Daniel Okafor"},
                    {"label": "Phone", "value": "07700 900461"},
                    {"label": "Membership", "value": "Adult"},
                ],
            }
        )

    async def describe_region(self, data_url: str) -> str:
        return f"A {_size(data_url)[0]} px wide region with a mark"

    async def ask(self, question: Question) -> str:
        if "whose" in question.question.lower():
            return json.dumps({"answer": "It is Daniel Okafor's form.", "quote": "Daniel Okafor"})
        return json.dumps({"answer": NOT_IN_DOCUMENT, "quote": ""})

    async def aclose(self) -> None:
        return None


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    origins = os.environ.get("CORS_ORIGINS", "http://127.0.0.1:3100").split(",")
    settings = Settings(meta_api_key="unused", cors_origins=tuple(origins))
    app = create_app(settings, FakeGateway())
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
