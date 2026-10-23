import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from dsc_backend.errors import PipelineError
from dsc_backend.main import create_app
from dsc_backend.privacy import Span
from dsc_backend.progress import ndjson_stream
from test_process import INVOICE_JSON, ExtractGateway, FakeGateway, _png, _settings

STREAM = {"accept": "application/x-ndjson"}


def _events(response) -> list[dict[str, object]]:
    return [json.loads(line) for line in response.text.splitlines() if line]


def _post(client: TestClient, headers: dict[str, str] | None = None, **data: str):
    return client.post(
        "/api/process",
        data=data,
        headers=headers or {},
        files={"image": ("note.png", _png(), "image/png")},
    )


class EveryStepGateway(ExtractGateway):
    async def sensitive_spans(self, text: str) -> list[Span]:
        return [Span("name", "Receipt", "model")]


def test_stages_stream_in_order_and_end_with_the_same_result() -> None:
    gateway = EveryStepGateway([INVOICE_JSON, INVOICE_JSON])
    with TestClient(create_app(_settings(), gateway)) as client:
        streamed = _post(client, STREAM, extract="true", redact="stamp", redact_text="true")
        plain = _post(client, extract="true", redact="stamp", redact_text="true")
    assert streamed.status_code == 200
    assert streamed.headers["content-type"].startswith("application/x-ndjson")
    assert streamed.headers["x-accel-buffering"] == "no"
    events = _events(streamed)
    assert events[0] == {
        "event": "stages",
        "stages": ["prepare", "segment", "transcribe", "proofread", "extract", "privacy", "render"],
    }
    done = [event["stage"] for event in events if event.get("status") == "done"]
    assert done[0] == "prepare"
    assert done[-1] == "render"
    assert set(done) == set(events[0]["stages"])  # type: ignore[arg-type]
    for stage in done:
        running = (
            events.index({"event": "stage", "stage": stage, "status": "running", "detail": None})
            if stage != "prepare"
            else -1
        )
        finished = next(
            i for i, e in enumerate(events) if e.get("stage") == stage and e.get("status") == "done"
        )
        assert running < finished
    segment = next(e for e in events if e.get("stage") == "segment" and e["status"] == "done")
    assert segment["detail"] == "stamp: 1, signature: 0, photograph: 0, rectangle: 0"
    assert events[-1]["event"] == "result"
    assert events[-1]["data"] == plain.json()


def test_without_the_header_the_endpoint_is_unchanged() -> None:
    with TestClient(create_app(_settings(), FakeGateway())) as client:
        response = _post(client)
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["cleaned_text"] == "Receipt total"


def test_upstream_failure_after_some_stages_is_an_error_event() -> None:
    gateway = FakeGateway(fail_with=TimeoutError("slow"))
    with TestClient(create_app(_settings(), gateway)) as client:
        response = _post(client, STREAM)
    assert response.status_code == 200
    events = _events(response)
    assert events[0]["event"] == "stages"
    assert events[-1] == {"event": "error", "status": 502, "detail": "The model request timed out"}
    assert not any(event["event"] == "result" for event in events)


def test_bad_input_is_a_plain_error_before_streaming() -> None:
    with TestClient(create_app(_settings(), FakeGateway())) as client:
        corrupt = client.post(
            "/api/process",
            headers=STREAM,
            files={"image": ("note.png", b"not-a-png", "image/png")},
        )
        blocked = _post(client, STREAM, custom="receipt")
    assert corrupt.status_code == 400
    assert corrupt.json()["detail"] == "Upload is not a valid JPEG or PNG image"
    assert blocked.status_code == 400


def test_only_requested_stages_are_planned() -> None:
    with TestClient(create_app(_settings(), FakeGateway())) as client:
        events = _events(_post(client, STREAM, concepts=" , "))
    assert events[0]["stages"] == ["prepare", "transcribe", "proofread", "render"]


def test_closing_the_stream_cancels_the_work() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def work(emit) -> dict[str, object]:
        await emit({"event": "stage", "stage": "prepare", "status": "done", "detail": None})
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return {}

    async def run() -> None:
        stream = ndjson_stream(work)
        first = await anext(stream)
        assert json.loads(first)["stage"] == "prepare"
        await started.wait()
        await stream.aclose()
        assert cancelled.is_set()

    asyncio.run(run())


def test_unexpected_failure_becomes_a_502_event() -> None:
    async def work(emit) -> dict[str, object]:
        raise ValueError("boom")

    async def collect() -> list[bytes]:
        return [line async for line in ndjson_stream(work)]

    lines = asyncio.run(collect())
    assert [json.loads(line) for line in lines] == [
        {"event": "error", "status": 502, "detail": "The model request failed"}
    ]


def test_pipeline_error_keeps_its_status() -> None:
    async def work(emit) -> dict[str, object]:
        raise PipelineError(502, "The model request failed")

    async def collect() -> list[bytes]:
        return [line async for line in ndjson_stream(work)]

    assert json.loads(asyncio.run(collect())[0])["status"] == 502


@pytest.mark.parametrize("accept", ["application/json", "*/*", ""])
def test_other_accept_headers_get_json(accept: str) -> None:
    with TestClient(create_app(_settings(), FakeGateway())) as client:
        response = _post(client, {"accept": accept} if accept else None)
    assert response.json()["original_text"] == "Reciept total"


def test_describe_stage_reports_how_many_were_described() -> None:
    class Notes(FakeGateway):
        async def describe_region(self, data_url: str) -> str:
            return "Stamp"

    with TestClient(create_app(_settings(), Notes())) as client:
        events = _events(_post(client, STREAM, describe="true"))
    assert events[0]["stages"][:3] == ["prepare", "segment", "describe"]  # type: ignore[index]
    done = next(e for e in events if e.get("stage") == "describe" and e["status"] == "done")
    assert done["detail"] == "1 of 1 described"
