import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress

from dsc_backend.errors import PipelineError

logger = logging.getLogger(__name__)

Event = dict[str, object]
Emit = Callable[[Event], Awaitable[None]]


async def _ignore(_event: Event) -> None:
    return None


class Progress:
    """Reports pipeline stages as events. Without an emitter it does nothing."""

    def __init__(self, emit: Emit | None = None) -> None:
        self._emit = emit or _ignore

    async def plan(self, stages: list[str]) -> None:
        await self._emit({"event": "stages", "stages": stages})

    async def done(self, stage: str, detail: str | None = None) -> None:
        await self._emit({"event": "stage", "stage": stage, "status": "done", "detail": detail})

    async def run[T](
        self,
        stage: str,
        call: Awaitable[T],
        detail: Callable[[T], str | None] | None = None,
    ) -> T:
        await self._emit({"event": "stage", "stage": stage, "status": "running", "detail": None})
        result = await call
        await self.done(stage, detail(result) if detail else None)
        return result


async def ndjson_stream(work: Callable[[Emit], Awaitable[Event]]) -> AsyncIterator[bytes]:
    """Run work in the background and stream its events, one JSON object per line.

    The last line is {"event": "result", "data": ...} or {"event": "error", ...}.
    If the client goes away, the generator is closed and the work is cancelled,
    so no further model calls are paid for.
    """
    queue: asyncio.Queue[Event | None] = asyncio.Queue()

    async def emit(event: Event) -> None:
        await queue.put(event)

    async def run() -> None:
        try:
            await queue.put({"event": "result", "data": await work(emit)})
        except PipelineError as exc:
            await queue.put({"event": "error", "status": exc.status_code, "detail": exc.message})
        except Exception as exc:
            logger.warning("stream failed: %s", type(exc).__name__)
            await queue.put({"event": "error", "status": 502, "detail": "The model request failed"})
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())
    try:
        while (item := await queue.get()) is not None:
            yield (json.dumps(item) + "\n").encode()
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
