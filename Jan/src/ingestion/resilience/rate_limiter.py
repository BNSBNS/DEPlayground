"""Rate limiter implementations.

Provides rate limiting to respect external API quotas and prevent overload.
"""

import asyncio
import time
from abc import ABC, abstractmethod
import structlog

logger = structlog.get_logger()


class RateLimiter(ABC):
    """Abstract base class for rate limiters."""

    @abstractmethod
    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire
        """
        ...

    @abstractmethod
    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False otherwise
        """
        ...

    @abstractmethod
    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        ...


class TokenBucketRateLimiter(RateLimiter):
    """Token bucket rate limiter.

    Allows bursts up to bucket capacity, then limits to steady rate.

    Example:
        ```python
        # Allow 10 requests/second with bursts up to 50
        limiter = TokenBucketRateLimiter(rate=10.0, capacity=50)

        async def make_request():
            await limiter.acquire()
            # ... make API call
        ```
    """

    def __init__(
        self,
        rate: float,
        capacity: int | None = None,
        name: str = "default",
    ):
        """Initialize token bucket.

        Args:
            rate: Tokens added per second (sustained rate)
            capacity: Maximum tokens in bucket (burst capacity)
                     Defaults to rate (1 second worth of tokens)
            name: Identifier for logging
        """
        self.rate = rate
        self.capacity = capacity if capacity is not None else int(rate)
        self.name = name

        self._tokens = float(self.capacity)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()
        self._total_acquired = 0
        self._total_waited_seconds = 0.0

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(
            self.capacity,
            self._tokens + elapsed * self.rate
        )
        self._last_update = now

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire

        Raises:
            ValueError: If tokens > capacity
        """
        if tokens > self.capacity:
            raise ValueError(
                f"Cannot acquire {tokens} tokens, "
                f"capacity is {self.capacity}"
            )

        async with self._lock:
            self._refill()

            while self._tokens < tokens:
                # Calculate wait time
                needed = tokens - self._tokens
                wait_time = needed / self.rate

                logger.debug(
                    "Rate limit reached, waiting",
                    limiter=self.name,
                    tokens_needed=needed,
                    wait_seconds=wait_time,
                )

                self._total_waited_seconds += wait_time
                await asyncio.sleep(wait_time)
                self._refill()

            self._tokens -= tokens
            self._total_acquired += tokens

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False otherwise
        """
        # Note: This is not async-safe for concurrent use
        # For async safety, use acquire() instead
        self._refill()

        if self._tokens >= tokens:
            self._tokens -= tokens
            self._total_acquired += tokens
            return True
        return False

    def get_available_tokens(self) -> float:
        """Get number of currently available tokens."""
        self._refill()
        return self._tokens

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        self._refill()
        return {
            "name": self.name,
            "rate": self.rate,
            "capacity": self.capacity,
            "available_tokens": self._tokens,
            "total_acquired": self._total_acquired,
            "total_waited_seconds": self._total_waited_seconds,
        }


class SlidingWindowRateLimiter(RateLimiter):
    """Sliding window rate limiter.

    More accurate than token bucket for strict rate limits,
    but uses more memory.

    Example:
        ```python
        # Allow exactly 60 requests per minute
        limiter = SlidingWindowRateLimiter(
            max_requests=60,
            window_seconds=60
        )
        ```
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        name: str = "default",
    ):
        """Initialize sliding window limiter.

        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Window size in seconds
            name: Identifier for logging
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name

        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()
        self._total_acquired = 0
        self._total_rejected = 0

    def _cleanup_old_entries(self) -> None:
        """Remove timestamps outside the window."""
        cutoff = time.monotonic() - self.window_seconds
        self._timestamps = [ts for ts in self._timestamps if ts > cutoff]

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire (each counts as one request)
        """
        for _ in range(tokens):
            async with self._lock:
                self._cleanup_old_entries()

                while len(self._timestamps) >= self.max_requests:
                    # Wait until oldest entry expires
                    oldest = self._timestamps[0]
                    wait_time = (
                        oldest + self.window_seconds - time.monotonic()
                    )
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    self._cleanup_old_entries()

                self._timestamps.append(time.monotonic())
                self._total_acquired += 1

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting."""
        self._cleanup_old_entries()

        if len(self._timestamps) + tokens <= self.max_requests:
            for _ in range(tokens):
                self._timestamps.append(time.monotonic())
                self._total_acquired += 1
            return True

        self._total_rejected += tokens
        return False

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        self._cleanup_old_entries()
        return {
            "name": self.name,
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "current_count": len(self._timestamps),
            "available": self.max_requests - len(self._timestamps),
            "total_acquired": self._total_acquired,
            "total_rejected": self._total_rejected,
        }
