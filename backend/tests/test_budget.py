import asyncio
import time

from fastapi.testclient import TestClient

from dsc_backend.budget import Budget
from dsc_backend.errors import PipelineError
from dsc_backend.main import create_app
from test_process import INVOICE_JSON, DescribeGateway, ExtractGateway, _post, _settings


def test_a_late_step_is_cut_and_named_a_failed_one_is_not() -> None:
    async def run() -> tuple[object, object, object, Budget]:
        budget = Budget(0.05)

        async def slow() -> str:
            await asyncio.sleep(5)
            return "late"

        async def broken() -> str:
            raise PipelineError(502, "The model request failed")

        async def quick() -> str:
            return "ok"

        late = await budget.optional(slow(), "Slow step")
        failed = await budget.optional(broken(), "Broken step")
        fine = await budget.optional(quick(), "Quick step")
        return late, failed, fine, budget

    late, failed, fine, budget = asyncio.run(run())
    assert (late, failed, fine) == (None, None, "ok")
    assert budget.cut == ["Slow step"]
    assert budget.warnings() == ["Slow step ran past the 0.05 second limit and was skipped."]


def test_a_step_started_after_the_deadline_is_cut_at_once() -> None:
    async def run() -> tuple[object, Budget, float]:
        budget = Budget(0.01)
        await asyncio.sleep(0.05)
        started = time.perf_counter()
        result = await budget.optional(asyncio.sleep(5, result="late"), "Late start")
        return result, budget, time.perf_counter() - started

    result, budget, took = asyncio.run(run())
    assert result is None
    assert budget.was_cut("Late start")
    assert took < 1


class SlowExtract(ExtractGateway):
    async def extract(self, text: str, problem: str | None = None) -> str:
        await asyncio.sleep(5)
        return INVOICE_JSON


def test_slow_optional_steps_are_skipped_but_the_core_result_comes_back() -> None:
    gateway = SlowExtract([INVOICE_JSON])
    started = time.perf_counter()
    with TestClient(create_app(_settings(request_budget_seconds=0.2), gateway)) as client:
        body = _post(client, extract="true").json()
    assert time.perf_counter() - started < 3
    assert body["cleaned_text"] == "Receipt total"
    assert body["document"] is None
    assert body["warnings"] == [
        "Pulling out key fields ran past the 0.2 second limit and was skipped."
    ]


class SlowProofread(DescribeGateway):
    async def proofread(self, text: str) -> str:
        await asyncio.sleep(0.3)
        return "Receipt total"


def test_core_steps_are_never_cut() -> None:
    gateway = SlowProofread()
    with TestClient(create_app(_settings(request_budget_seconds=0.1), gateway)) as client:
        body = _post(client, describe="true").json()
    # The proofread outlives the budget and still finishes. The description
    # ran before the deadline, so it is kept.
    assert body["cleaned_text"] == "Receipt total"
    assert body["boxes"][0]["description"] == "Small square stamp"
    assert body["warnings"] == []
