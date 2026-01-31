"""Circuit Breaker pattern implementation.

Prevents cascading failures by temporarily stopping requests to failing services.
Based on Michael Nygard's "Release It!" pattern.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Failures exceeded threshold, requests are rejected immediately
- HALF_OPEN: Testing if service has recovered
"""

import asyncio
from datetime import datetime, UTC
from enum import Enum
from typing import Callable, TypeVar, ParamSpec
import structlog

logger = structlog.get_logger()

P = ParamSpec("P")
T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitOpenError(Exception):
    """Raised when circuit is open and rejecting requests."""

    def __init__(self, name: str, remaining_seconds: float):
        self.name = name
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit '{name}' is open. "
            f"Retry in {remaining_seconds:.1f} seconds."
        )


class CircuitBreaker:
    """Circuit breaker for protecting external service calls.

    Example:
        ```python
        cb = CircuitBreaker("finnhub", failure_threshold=5)

        async with cb:
            await fetch_from_finnhub()

        # Or functional style:
        result = await cb.call(fetch_from_finnhub)
        ```
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 30,
        half_open_max_calls: int = 3,
        excluded_exceptions: tuple[type[Exception], ...] | None = None,
    ):
        """Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker
            failure_threshold: Number of failures before opening circuit
            recovery_timeout_seconds: Time to wait before testing recovery
            half_open_max_calls: Successful calls needed to close circuit
            excluded_exceptions: Exceptions that don't count as failures
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        self.excluded_exceptions = excluded_exceptions or ()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return True

        elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _get_remaining_timeout(self) -> float:
        """Get remaining seconds until circuit can be tested."""
        if self._last_failure_time is None:
            return 0.0

        elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()
        return max(0.0, self.recovery_timeout - elapsed)

    def _on_success(self) -> None:
        """Handle successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            logger.debug(
                "Circuit half-open success",
                circuit=self.name,
                success_count=self._success_count,
                required=self.half_open_max_calls,
            )
            if self._success_count >= self.half_open_max_calls:
                self._close_circuit()
        else:
            # Reset failure count on success in closed state
            self._failure_count = 0

    def _on_failure(self, error: Exception) -> None:
        """Handle failed call."""
        # Don't count excluded exceptions
        if isinstance(error, self.excluded_exceptions):
            return

        self._failure_count += 1
        self._last_failure_time = datetime.now(UTC)

        logger.warning(
            "Circuit failure recorded",
            circuit=self.name,
            failure_count=self._failure_count,
            threshold=self.failure_threshold,
            error=str(error),
        )

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open returns to open
            self._open_circuit()
        elif self._failure_count >= self.failure_threshold:
            self._open_circuit()

    def _open_circuit(self) -> None:
        """Transition to open state."""
        self._state = CircuitState.OPEN
        self._success_count = 0
        logger.warning(
            "Circuit opened",
            circuit=self.name,
            failure_count=self._failure_count,
            recovery_timeout=self.recovery_timeout,
        )

    def _close_circuit(self) -> None:
        """Transition to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        logger.info("Circuit closed", circuit=self.name)

    async def call(
        self,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Execute function through circuit breaker.

        Args:
            func: Async or sync function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            CircuitOpenError: If circuit is open
            Exception: Any exception from func (after recording failure)
        """
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info("Circuit entering half-open state", circuit=self.name)
                else:
                    raise CircuitOpenError(self.name, self._get_remaining_timeout())

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            async with self._lock:
                self._on_success()

            return result

        except Exception as e:
            async with self._lock:
                self._on_failure(e)
            raise

    async def __aenter__(self) -> "CircuitBreaker":
        """Context manager entry - check if circuit allows requests."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                else:
                    raise CircuitOpenError(self.name, self._get_remaining_timeout())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit - record success or failure."""
        async with self._lock:
            if exc_type is None:
                self._on_success()
            elif exc_val is not None:
                self._on_failure(exc_val)
        return False  # Don't suppress exceptions

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        logger.info("Circuit manually reset", circuit=self.name)

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure": (
                self._last_failure_time.isoformat()
                if self._last_failure_time
                else None
            ),
        }
