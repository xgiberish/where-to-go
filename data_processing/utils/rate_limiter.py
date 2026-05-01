"""Rate limiting utilities for respectful scraping."""
import asyncio
import time


class RateLimiter:
    """Simple interval-based rate limiter.

    Enforces a minimum interval between requests so we never exceed
    `requests_per_second` on average.
    """

    def __init__(self, requests_per_second: float = 0.5) -> None:
        self._min_interval = 1.0 / requests_per_second
        self._last_request: float = 0.0

    async def acquire(self) -> None:
        """Sleep if necessary to honour the rate limit."""
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()
