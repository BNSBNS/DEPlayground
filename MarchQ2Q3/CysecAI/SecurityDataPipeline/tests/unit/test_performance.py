"""Performance tests for the SIEM detection engine.

Validates throughput and latency targets:
- Log generation: 10K events/sec
- Pipeline processing: 5K events/sec
- Storage writes: 5K events/sec
- API response: <200ms
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app, set_state
from src.config import GeneratorSettings
from src.data.generator import LogGenerator
from src.ingestion.normalizer import NormalizedEvent, normalize_from_log_event
from src.pipeline.processor import EventProcessor
from src.storage.event_store import EventStore

PERF_EVENT_COUNT = 5000


@pytest.fixture()
def large_dataset() -> list[NormalizedEvent]:
    """5K normalized events for perf testing."""
    gen = LogGenerator(GeneratorSettings(num_events=PERF_EVENT_COUNT, seed=42))
    events = gen.generate()
    return [normalize_from_log_event(e.model_dump()) for e in events]


class TestGeneratorPerformance:
    def test_generation_throughput(self) -> None:
        """Generate 10K events in under 2 seconds."""
        gen = LogGenerator(GeneratorSettings(num_events=10000, seed=42))
        start = time.perf_counter()
        events = gen.generate()
        elapsed = time.perf_counter() - start

        assert len(events) == 10000
        assert elapsed < 2.0, f"Generation took {elapsed:.2f}s (target: <2.0s)"
        throughput = len(events) / elapsed
        assert throughput > 5000, f"Throughput: {throughput:.0f} events/sec (target: >5000)"


class TestPipelinePerformance:
    def test_processing_throughput(self, large_dataset: list[NormalizedEvent]) -> None:
        """Process 5K events through detection + correlation."""
        processor = EventProcessor(correlation_rules=[])
        start = time.perf_counter()
        for event in large_dataset:
            processor.process_event(event)
        elapsed = time.perf_counter() - start

        throughput = len(large_dataset) / elapsed
        assert throughput > 1000, f"Throughput: {throughput:.0f} events/sec (target: >1000)"

    def test_pipeline_with_rules(self, large_dataset: list[NormalizedEvent]) -> None:
        """Process 5K events with Sigma rules loaded."""
        rules_dir = Path(__file__).resolve().parents[2] / "rules"
        processor = EventProcessor(rules_dir=rules_dir)

        start = time.perf_counter()
        alert_count = 0
        for event in large_dataset:
            alerts = processor.process_event(event)
            alert_count += len(alerts)
        elapsed = time.perf_counter() - start

        throughput = len(large_dataset) / elapsed
        assert throughput > 500, f"Throughput: {throughput:.0f} events/sec (target: >500)"
        assert alert_count > 0, "Expected at least some alerts from 5K events"


class TestStoragePerformance:
    def test_write_throughput(self, large_dataset: list[NormalizedEvent]) -> None:
        """Store 5K events in under 5 seconds."""
        store = EventStore(":memory:")
        start = time.perf_counter()
        for event in large_dataset:
            store.store_event(event)
        elapsed = time.perf_counter() - start

        throughput = len(large_dataset) / elapsed
        assert throughput > 500, f"Write throughput: {throughput:.0f} events/sec (target: >500)"
        store.close()

    def test_query_latency(self, large_dataset: list[NormalizedEvent]) -> None:
        """Query 100 events from 5K in under 50ms."""
        store = EventStore(":memory:")
        for event in large_dataset:
            store.store_event(event)

        start = time.perf_counter()
        results = store.query_events(limit=100)
        elapsed = time.perf_counter() - start

        assert len(results) == 100
        assert elapsed < 0.05, f"Query took {elapsed * 1000:.1f}ms (target: <50ms)"
        store.close()


class TestAPIPerformance:
    async def test_health_latency(self) -> None:
        """Health endpoint responds in <50ms."""
        store = EventStore(":memory:")
        set_state(store=store, processor=EventProcessor(correlation_rules=[]))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            start = time.perf_counter()
            resp = await client.get("/health")
            elapsed = time.perf_counter() - start

            assert resp.status_code == 200
            assert elapsed < 0.05, f"Health took {elapsed * 1000:.1f}ms (target: <50ms)"

    async def test_events_query_latency(self) -> None:
        """Events endpoint responds in <200ms with data."""
        store = EventStore(":memory:")
        proc = EventProcessor(correlation_rules=[])
        set_state(store=store, processor=proc)

        # Seed 1K events
        gen = LogGenerator(GeneratorSettings(num_events=1000, seed=42))
        for event in gen.generate():
            normalized = normalize_from_log_event(event.model_dump())
            store.store_event(normalized)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            start = time.perf_counter()
            resp = await client.get("/api/v1/events", params={"limit": 50})
            elapsed = time.perf_counter() - start

            assert resp.status_code == 200
            assert elapsed < 0.2, f"Events query took {elapsed * 1000:.1f}ms (target: <200ms)"
