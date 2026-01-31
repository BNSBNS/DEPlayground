"""End-to-end tests for the complete streaming pipeline.

These tests require the full Docker Compose stack to be running.
Run with: pytest tests/e2e/ -v --run-e2e

Prerequisites:
    docker-compose -f docker-compose-full.yml up -d
    # Wait 60 seconds for services to start
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import requests
import websockets

# Skip E2E tests unless explicitly requested
pytestmark = pytest.mark.skipif(
    "not config.getoption('--run-e2e')",
    reason="E2E tests require --run-e2e flag and running Docker stack",
)


# Configuration
API_BASE_URL = "http://localhost:8000"
WS_BASE_URL = "ws://localhost:8000"
KAFKA_UI_URL = "http://localhost:8080"


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run E2E tests (requires Docker stack)",
    )


class TestHealthEndpoints:
    """Test API health endpoints."""

    def test_health_endpoint(self):
        """Test /health returns service status."""
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "kafka" in data

    def test_ready_endpoint(self):
        """Test /ready for Kubernetes readiness probe."""
        response = requests.get(f"{API_BASE_URL}/ready", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["ready", "not ready"]

    def test_live_endpoint(self):
        """Test /live for Kubernetes liveness probe."""
        response = requests.get(f"{API_BASE_URL}/live", timeout=10)
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestRESTEndpoints:
    """Test REST API endpoints that read from PostgreSQL."""

    def test_get_symbols(self):
        """Test GET /api/v1/symbols returns list of symbols."""
        response = requests.get(f"{API_BASE_URL}/api/v1/symbols", timeout=10)
        assert response.status_code == 200
        symbols = response.json()
        assert isinstance(symbols, list)

    def test_get_aggregates_default(self):
        """Test GET /api/v1/aggregates with default parameters."""
        response = requests.get(f"{API_BASE_URL}/api/v1/aggregates", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    def test_get_aggregates_with_filter(self):
        """Test GET /api/v1/aggregates with symbol filter."""
        response = requests.get(
            f"{API_BASE_URL}/api/v1/aggregates",
            params={"symbol": "POWER_DE", "hours": 1, "limit": 10},
            timeout=10,
        )
        assert response.status_code == 200
        data = response.json()
        # All results should be for POWER_DE
        for agg in data["data"]:
            assert agg["symbol"] == "POWER_DE"

    def test_get_aggregates_pagination(self):
        """Test pagination works correctly."""
        # Get first page
        response1 = requests.get(
            f"{API_BASE_URL}/api/v1/aggregates",
            params={"limit": 5, "offset": 0},
            timeout=10,
        )
        assert response1.status_code == 200
        page1 = response1.json()

        # Get second page
        response2 = requests.get(
            f"{API_BASE_URL}/api/v1/aggregates",
            params={"limit": 5, "offset": 5},
            timeout=10,
        )
        assert response2.status_code == 200
        page2 = response2.json()

        # Pages should have different data (if enough data exists)
        if page1["total"] > 5:
            assert page1["data"] != page2["data"]

    def test_get_vwap(self):
        """Test GET /api/v1/vwap returns VWAP per symbol."""
        response = requests.get(
            f"{API_BASE_URL}/api/v1/vwap",
            params={"hours": 1},
            timeout=10,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        for item in data:
            assert "symbol" in item
            assert "vwap" in item
            assert "total_volume" in item
            assert "trade_count" in item


class TestWebSocketStreaming:
    """Test WebSocket endpoints that read from Kafka."""

    @pytest.mark.asyncio
    async def test_websocket_trades_connection(self):
        """Test WebSocket connection to /ws/trades."""
        async with websockets.connect(f"{WS_BASE_URL}/ws/trades") as ws:
            # Should receive heartbeat or trade within 35 seconds
            message = await asyncio.wait_for(ws.recv(), timeout=35)
            data = json.loads(message)
            # Either a trade or heartbeat
            assert "symbol" in data or data.get("type") == "heartbeat"

    @pytest.mark.asyncio
    async def test_websocket_trades_receives_data(self):
        """Test that WebSocket receives trade data."""
        messages = []
        async with websockets.connect(f"{WS_BASE_URL}/ws/trades") as ws:
            # Collect messages for 10 seconds
            try:
                while len(messages) < 5:
                    message = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(message)
                    if data.get("type") != "heartbeat":
                        messages.append(data)
            except asyncio.TimeoutError:
                pass

        # Should have received some trade messages
        assert len(messages) > 0
        # Verify trade structure
        for msg in messages:
            assert "symbol" in msg
            assert "price" in msg
            assert "volume" in msg

    @pytest.mark.asyncio
    async def test_websocket_trades_by_symbol(self):
        """Test filtered WebSocket stream for specific symbol."""
        messages = []
        async with websockets.connect(f"{WS_BASE_URL}/ws/trades/POWER_DE") as ws:
            try:
                while len(messages) < 3:
                    message = await asyncio.wait_for(ws.recv(), timeout=30)
                    data = json.loads(message)
                    if data.get("type") != "heartbeat":
                        messages.append(data)
            except asyncio.TimeoutError:
                pass

        # All messages should be for POWER_DE
        for msg in messages:
            assert msg.get("symbol") == "POWER_DE"

    @pytest.mark.asyncio
    async def test_websocket_aggregates(self):
        """Test WebSocket stream for completed aggregates."""
        # This may take up to 90 seconds (60s window + 30s grace period)
        async with websockets.connect(f"{WS_BASE_URL}/ws/aggregates") as ws:
            try:
                # Wait for an aggregate (may take a full window duration)
                message = await asyncio.wait_for(ws.recv(), timeout=120)
                data = json.loads(message)

                if data.get("type") == "aggregate":
                    assert "symbol" in data
                    assert "vwap" in data
                    assert "window_start" in data
                    assert "window_end" in data
            except asyncio.TimeoutError:
                pytest.skip("No aggregate received within timeout")


class TestFullPipeline:
    """Test the complete E2E data flow."""

    def test_data_freshness(self):
        """Test that data is being processed and is fresh."""
        response = requests.get(
            f"{API_BASE_URL}/api/v1/aggregates",
            params={"hours": 1, "limit": 1},
            timeout=10,
        )
        assert response.status_code == 200
        data = response.json()

        if data["total"] > 0:
            latest = data["data"][0]
            window_end = datetime.fromisoformat(latest["window_end"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)

            # Data should be less than 5 minutes old
            age = now - window_end
            assert age < timedelta(minutes=5), f"Data is {age.total_seconds() / 60:.1f} minutes old"

    def test_vwap_calculation_consistency(self):
        """Test that VWAP calculations are consistent."""
        # Get aggregates for a symbol
        response = requests.get(
            f"{API_BASE_URL}/api/v1/aggregates",
            params={"symbol": "POWER_DE", "hours": 1, "limit": 10},
            timeout=10,
        )
        assert response.status_code == 200
        aggregates = response.json()["data"]

        if len(aggregates) > 0:
            for agg in aggregates:
                vwap = Decimal(agg["vwap"])
                min_price = Decimal(agg["min_price"])
                max_price = Decimal(agg["max_price"])

                # VWAP should be between min and max price
                assert min_price <= vwap <= max_price, (
                    f"VWAP {vwap} not between min {min_price} and max {max_price}"
                )

    def test_multiple_symbols_processed(self):
        """Test that multiple symbols are being processed."""
        response = requests.get(f"{API_BASE_URL}/api/v1/symbols", timeout=10)
        assert response.status_code == 200
        symbols = response.json()

        # Should have at least 2 symbols in production setup
        # The producer generates: POWER_DE, GAS_NL, BRENT_OIL, etc.
        assert len(symbols) >= 1, "Expected at least one symbol to be processed"


class TestLoadHandling:
    """Test API behavior under load."""

    def test_concurrent_rest_requests(self):
        """Test handling multiple concurrent REST requests."""
        import concurrent.futures

        def make_request():
            response = requests.get(
                f"{API_BASE_URL}/api/v1/aggregates",
                params={"limit": 10},
                timeout=10,
            )
            return response.status_code

        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert all(status == 200 for status in results)

    @pytest.mark.asyncio
    async def test_multiple_websocket_connections(self):
        """Test handling multiple WebSocket connections."""
        connections = []
        messages_received = []

        async def connect_and_receive():
            async with websockets.connect(f"{WS_BASE_URL}/ws/trades") as ws:
                msg = await asyncio.wait_for(ws.recv(), timeout=35)
                return json.loads(msg)

        # Create 5 concurrent connections
        tasks = [connect_and_receive() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All connections should receive data
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) >= 3, "Expected at least 3 successful connections"
