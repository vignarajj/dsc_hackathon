import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    """Sliding one-minute window per client key, held in memory.

    This is enough for one hosted process. It resets on restart and is not
    shared between workers.
    """

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._per_minute = per_minute
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        if self._per_minute <= 0:
            return True
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= 60:
            hits.popleft()
        if len(hits) >= self._per_minute:
            return False
        hits.append(now)
        self._prune(now)
        return True

    def _prune(self, now: float) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or now - hits[-1] >= 60]
        for key in stale:
            del self._hits[key]
