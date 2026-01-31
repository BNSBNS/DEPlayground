"""Retry logic with exponential backoff.

Provides automatic retry with configurable backoff strategies.
"""

import asyncio
import random
from dataclasses import dataclass, field
from typing import Callable, TypeVar, ParamSpec, Awaitable
import structlog

logger = structlog.get_logger()

P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class RetryPolicy:
    """Configuration for retry behavior.

    Example:
        ```python
        policy = RetryPolicy(
            max_retries=5,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=True
        )
        ```
    """

    max_retries: int = 3
    base_delay: float = 1.0  # Initial delay in seconds
    max_delay: float = 60.0  # Maximum delay cap
    exponential_base: float = 2.0  # Multiplier for exponential backoff
    jitter: bool = True  # Add randomness to prevent thundering herd
    jitter_factor: float = 0.1  # Jitter as fraction of delay

    # Exceptions to retry on (None = all exceptions)
    retryable_exceptions: tuple[type[Exception], ...] | None = None

    # Exceptions to never retry on
    fatal_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (KeyboardInterrupt, SystemExit)
    )

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0.0, delay)  # Ensure non-negative

        return delay

    def should_retry(self, exception: Exception) -> bool:
        """Check if exception should be retried.

        Args:
            exception: The exception that occurred

        Returns:
            True if should retry, False otherwise
        """
        # Never retry fatal exceptions
        if isinstance(exception, self.fatal_exceptions):
            return False

        # If retryable list is specified, only retry those
        if self.retryable_exceptions is not None:
            return isinstance(exception, self.retryable_exceptions)

        # Default: retry all non-fatal exceptions
        return True


class RetryExhaustedError(Exception):
    """Raised when all retries are exhausted."""

    def __init__(
        self,
        message: str,
        last_exception: Exception,
        attempts: int,
    ):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


async def retry_with_backoff(
    func: Callable[P, Awaitable[T]],
    *args: P.args,
    policy: RetryPolicy | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
    **kwargs: P.kwargs,
) -> T:
    """Execute async function with retry and exponential backoff.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        policy: Retry policy (uses defaults if None)
        on_retry: Callback called on each retry (attempt, error, delay)
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        RetryExhaustedError: If all retries are exhausted
        Exception: Fatal exceptions are raised immediately

    Example:
        ```python
        async def fetch_data():
            response = await httpx.get("https://api.example.com")
            return response.json()

        policy = RetryPolicy(max_retries=3, base_delay=1.0)
        data = await retry_with_backoff(fetch_data, policy=policy)
        ```
    """
    policy = policy or RetryPolicy()
    last_exception: Exception | None = None

    for attempt in range(policy.max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except Exception as e:
            last_exception = e

            # Check if we should retry
            if not policy.should_retry(e):
                logger.warning(
                    "Non-retryable exception, failing immediately",
                    exception_type=type(e).__name__,
                    error=str(e),
                )
                raise

            # Check if retries exhausted
            if attempt >= policy.max_retries:
                break

            # Calculate delay
            delay = policy.get_delay(attempt)

            logger.warning(
                "Retry attempt",
                attempt=attempt + 1,
                max_retries=policy.max_retries,
                delay_seconds=delay,
                exception_type=type(e).__name__,
                error=str(e),
            )

            # Call retry callback if provided
            if on_retry:
                on_retry(attempt + 1, e, delay)

            # Wait before retry
            await asyncio.sleep(delay)

    # All retries exhausted
    raise RetryExhaustedError(
        f"All {policy.max_retries + 1} attempts failed",
        last_exception=last_exception,  # type: ignore
        attempts=policy.max_retries + 1,
    )


def retry_decorator(
    policy: RetryPolicy | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
):
    """Decorator for adding retry logic to async functions.

    Args:
        policy: Retry policy
        on_retry: Callback called on each retry

    Example:
        ```python
        @retry_decorator(policy=RetryPolicy(max_retries=3))
        async def fetch_data():
            return await api_call()
        ```
    """
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await retry_with_backoff(
                func,
                *args,
                policy=policy,
                on_retry=on_retry,
                **kwargs,
            )
        return wrapper
    return decorator


class RetryContext:
    """Context manager for manual retry control.

    Example:
        ```python
        async with RetryContext(policy) as ctx:
            while ctx.should_continue():
                try:
                    result = await risky_operation()
                    ctx.success()
                    break
                except Exception as e:
                    await ctx.failed(e)
        ```
    """

    def __init__(self, policy: RetryPolicy | None = None):
        self.policy = policy or RetryPolicy()
        self._attempt = 0
        self._succeeded = False
        self._last_exception: Exception | None = None

    @property
    def attempt(self) -> int:
        """Current attempt number (0-indexed)."""
        return self._attempt

    def should_continue(self) -> bool:
        """Check if should continue retrying."""
        if self._succeeded:
            return False
        return self._attempt <= self.policy.max_retries

    def success(self) -> None:
        """Mark operation as successful."""
        self._succeeded = True

    async def failed(self, exception: Exception) -> None:
        """Record failure and wait for next retry.

        Args:
            exception: The exception that occurred

        Raises:
            Exception: If non-retryable or retries exhausted
        """
        self._last_exception = exception

        if not self.policy.should_retry(exception):
            raise exception

        if self._attempt >= self.policy.max_retries:
            raise RetryExhaustedError(
                f"All {self.policy.max_retries + 1} attempts failed",
                last_exception=exception,
                attempts=self._attempt + 1,
            )

        delay = self.policy.get_delay(self._attempt)
        self._attempt += 1

        logger.warning(
            "Retry context: waiting for next attempt",
            attempt=self._attempt,
            delay=delay,
            error=str(exception),
        )

        await asyncio.sleep(delay)

    async def __aenter__(self) -> "RetryContext":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False  # Don't suppress exceptions
