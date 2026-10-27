import asyncio
import logging
from collections.abc import Awaitable

logger = logging.getLogger(__name__)


class Budget:
    """One deadline for every optional step of a request.

    Core steps (segmentation, transcription, proofread) keep their own model
    timeouts and are never cut. An optional step still running at the deadline
    is cancelled, and its name is kept so the response can say what was skipped.
    """

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self._deadline = asyncio.get_running_loop().time() + seconds
        self.cut: list[str] = []

    async def optional[T](self, call: Awaitable[T], step: str) -> T | None:
        """Run a step whose failure, or lateness, must not fail the request."""
        limit = asyncio.timeout_at(self._deadline)
        try:
            async with limit:
                return await call
        except Exception as exc:
            if limit.expired():
                self.cut.append(step)
            else:
                logger.warning("optional step failed: %s", type(exc).__name__)
            return None

    def was_cut(self, step: str) -> bool:
        return step in self.cut

    def warnings(self) -> list[str]:
        return [
            f"{step} ran past the {self.seconds:g} second limit and was skipped."
            for step in self.cut
        ]
