from dsc_backend.ratelimit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_zero_means_no_limit() -> None:
    limiter = RateLimiter(0)
    assert all(limiter.allow("a") for _ in range(100))


def test_limit_applies_per_client_and_resets_after_a_minute() -> None:
    clock = Clock()
    limiter = RateLimiter(2, clock=clock)
    assert limiter.allow("a")
    assert limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")
    clock.now = 60.0
    assert limiter.allow("a")
