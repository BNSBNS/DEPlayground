"""Resilience patterns for fault-tolerant data ingestion.

This module provides cross-cutting concerns for building resilient connectors:
- Circuit Breaker: Prevent cascading failures
- Rate Limiter: Respect external API limits
- Backpressure: Handle producer/consumer speed mismatches
- Retry: Automatic retry with exponential backoff
"""

from ingestion.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
)
from ingestion.resilience.rate_limiter import (
    RateLimiter,
    TokenBucketRateLimiter,
)
from ingestion.resilience.backpressure import (
    BackpressureHandler,
    BackpressureStrategy,
)
from ingestion.resilience.retry import (
    RetryPolicy,
    retry_with_backoff,
)

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitOpenError",
    "RateLimiter",
    "TokenBucketRateLimiter",
    "BackpressureHandler",
    "BackpressureStrategy",
    "RetryPolicy",
    "retry_with_backoff",
]
