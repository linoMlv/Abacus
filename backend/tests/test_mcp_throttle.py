"""The in-memory sliding-window limiter guarding the /mcp transport."""

from mcp_server.throttle import SlidingWindowLimiter


def test_allows_up_to_the_limit_then_blocks():
    limiter = SlidingWindowLimiter(limit=3, window=60)
    # Same key (IP), fixed instant: first 3 pass, the 4th is blocked.
    assert [limiter.allow("ip", now=0) for _ in range(4)] == [True, True, True, False]


def test_window_slides_so_old_hits_expire():
    limiter = SlidingWindowLimiter(limit=2, window=10)
    assert limiter.allow("ip", now=0) is True
    assert limiter.allow("ip", now=1) is True
    assert limiter.allow("ip", now=2) is False  # full
    # Once the first two hits fall outside the 10s window, room frees up.
    assert limiter.allow("ip", now=12) is True


def test_keys_are_independent():
    limiter = SlidingWindowLimiter(limit=1, window=60)
    assert limiter.allow("a", now=0) is True
    assert limiter.allow("b", now=0) is True  # different IP, own budget
    assert limiter.allow("a", now=0) is False
