"""Webhook connector - receives push notifications via HTTP.

Runs an HTTP server to receive webhooks from external services.
"""

import asyncio
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request, HTTPException
import uvicorn

from ingestion.adapters.connectors.base import BaseConnector
from ingestion.domain.models import SourceType
from ingestion.ports import MetricsPort
from ingestion.resilience import CircuitBreaker, RetryPolicy


class WebhookConnector(BaseConnector):
    """Webhook connector - HTTP server for receiving push notifications.

    Example:
        ```python
        connector = WebhookConnector(
            name="finnhub_events",
            port=8080,
            path="/webhook",
            secret_header="X-Finnhub-Secret",
            secret_value="your-secret",
        )

        async for event in connector.stream_events():
            process(event)
        ```
    """

    def __init__(
        self,
        name: str,
        port: int = 8080,
        host: str = "0.0.0.0",
        path: str = "/webhook",
        secret_header: str | None = None,
        secret_value: str | None = None,
        queue_size: int = 10000,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        metrics: MetricsPort | None = None,
    ):
        """Initialize webhook connector.

        Args:
            name: Connector identifier
            port: HTTP server port
            host: HTTP server host
            path: Webhook endpoint path
            secret_header: Header name for authentication
            secret_value: Expected secret value
            queue_size: Maximum events to buffer
            circuit_breaker: Optional circuit breaker
            retry_policy: Optional retry policy
            metrics: Optional metrics port
        """
        super().__init__(
            name=name,
            source_type=SourceType.WEBHOOK,
            expected_latency_ms=50,  # Event-driven, minimal latency
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
            metrics=metrics,
        )

        self._port = port
        self._host = host
        self._path = path
        self._secret_header = secret_header
        self._secret_value = secret_value
        self._queue_size = queue_size

        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=queue_size
        )
        self._app: FastAPI | None = None
        self._server: uvicorn.Server | None = None
        self._server_task: asyncio.Task | None = None
        self._received_count = 0
        self._rejected_count = 0

    def _create_app(self) -> FastAPI:
        """Create FastAPI application for receiving webhooks."""
        app = FastAPI(
            title=f"Webhook Receiver: {self._name}",
            docs_url=None,  # Disable docs in production
            redoc_url=None,
        )

        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "connector": self._name,
                "queue_size": self._queue.qsize(),
                "received_count": self._received_count,
            }

        @app.post(self._path)
        async def receive_webhook(request: Request):
            """Receive webhook payload."""
            # Validate secret if configured
            if self._secret_header and self._secret_value:
                received_secret = request.headers.get(self._secret_header)
                if received_secret != self._secret_value:
                    self._rejected_count += 1
                    self._logger.warning(
                        "Webhook rejected: invalid secret",
                        header=self._secret_header,
                    )
                    raise HTTPException(status_code=401, detail="Invalid secret")

            try:
                payload = await request.json()
            except Exception as e:
                self._rejected_count += 1
                raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

            # Try to queue the event
            try:
                self._queue.put_nowait(payload)
                self._received_count += 1
                return {"status": "accepted", "queue_size": self._queue.qsize()}
            except asyncio.QueueFull:
                self._rejected_count += 1
                self._logger.warning("Webhook queue full, rejecting")
                raise HTTPException(
                    status_code=503,
                    detail="Queue full, try again later"
                )

        return app

    async def connect(self) -> None:
        """Start the webhook HTTP server."""
        self._logger.info(
            "Starting webhook server",
            host=self._host,
            port=self._port,
            path=self._path,
        )

        self._app = self._create_app()

        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
            log_level="warning",  # Reduce uvicorn logging
        )
        self._server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(self._server.serve())

        # Wait for server to be ready
        while not self._server.started:
            await asyncio.sleep(0.1)

        self._logger.info("Webhook server started")

    async def disconnect(self) -> None:
        """Stop the webhook HTTP server."""
        if self._server:
            self._server.should_exit = True

        if self._server_task:
            try:
                await asyncio.wait_for(self._server_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._server_task.cancel()
                try:
                    await self._server_task
                except asyncio.CancelledError:
                    pass

        self._server = None
        self._server_task = None
        self._app = None
        self._logger.info("Webhook server stopped")

    async def _fetch_events(self) -> AsyncIterator[dict[str, Any]]:
        """Yield events from the queue as they arrive."""
        while self._running:
            try:
                # Wait for events with timeout to allow checking _running
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                yield event

            except asyncio.TimeoutError:
                # No event received, continue loop to check _running
                continue

    async def health_check(self) -> bool:
        """Check if webhook server is healthy."""
        return (
            self._connected
            and self._running
            and self._server is not None
            and self._server.started
        )

    def get_stats(self) -> dict[str, Any]:
        """Get connector statistics."""
        stats = super().get_stats()
        stats.update({
            "host": self._host,
            "port": self._port,
            "path": self._path,
            "queue_size": self._queue.qsize(),
            "queue_max_size": self._queue_size,
            "received_count": self._received_count,
            "rejected_count": self._rejected_count,
            "server_started": (
                self._server.started if self._server else False
            ),
        })
        return stats
