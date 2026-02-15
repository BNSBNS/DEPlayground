"""Configuration management using pydantic-settings.

This module provides centralized configuration with validation for all services.
Configuration is loaded from environment variables following 12-factor app principles.
"""

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionMode(str, Enum):
    """Ingestion mode determines which data sources are active.

    Modes:
        LOCAL: Use synthetic producer (Docker) - no external APIs
        REALTIME: Use real-time APIs (WebSocket, SSE, Polling)
        BATCH: Use batch file processing (CSV, Parquet)
        HYBRID: Combine real-time APIs and batch processing
    """

    LOCAL = "local"
    REALTIME = "realtime"
    BATCH = "batch"
    HYBRID = "hybrid"


class KafkaSettings(BaseSettings):
    """Kafka connection and topic configuration."""

    model_config = SettingsConfigDict(
        env_prefix="KAFKA_",
        extra="ignore",
    )

    bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Comma-separated list of Kafka broker addresses",
    )
    topic: str = Field(
        default="trades",
        description="Main topic for trade events",
    )
    dlq_topic: str = Field(
        default="trades-dlq",
        description="Dead Letter Queue topic for failed messages",
    )
    consumer_group: str = Field(
        default="trade-aggregator",
        description="Consumer group ID for the streaming consumer",
    )

    # Topic durability settings
    replication_factor: int = Field(
        default=1,
        ge=1,
        le=9,
        description="Replication factor for topic creation. Use 3+ in production.",
    )
    min_insync_replicas: int = Field(
        default=1,
        ge=1,
        le=9,
        description="min.insync.replicas for topic creation. Use 2+ in production.",
    )

    # Producer settings (hardcoded for trading durability requirements)
    # These are documented here but set in kafka_utils.py
    # acks: all (wait for all replicas)
    # enable.idempotence: true (exactly-once producer semantics)

    @field_validator("bootstrap_servers")
    @classmethod
    def validate_bootstrap_servers(cls, v: str) -> str:
        """Validate bootstrap servers format."""
        if not v or not v.strip():
            raise ValueError("bootstrap_servers cannot be empty")
        return v


class PostgresSettings(BaseSettings):
    """PostgreSQL connection configuration."""

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        extra="ignore",
    )

    user: str = Field(default="trading")
    password: str = Field(default="trading")
    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    db: str = Field(default="trades")

    # Alternative: full DSN (takes precedence if set)
    dsn: str | None = Field(
        default=None,
        description="Full PostgreSQL connection string (overrides individual settings)",
    )

    # Connection pool settings (Fix #7)
    pool_min: int = Field(
        default=2,
        ge=1,
        le=20,
        description="Minimum connections in pool",
    )
    pool_max: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum connections in pool",
    )
    pool_recycle: int = Field(
        default=1800,
        ge=300,
        le=7200,
        description="Recycle connections after N seconds (avoid stale sockets)",
    )
    pool_pre_ping: bool = Field(
        default=True,
        description="Health check connections before use",
    )
    pool_timeout: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Timeout waiting for connection from pool (seconds)",
    )

    # Retry settings (Fix #1)
    retry_max: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for DB operations",
    )
    retry_backoff: list[int] = Field(
        default=[1, 2, 4],
        description="Backoff delays in seconds for each retry attempt",
    )

    def get_dsn(self) -> str:
        """Get the PostgreSQL connection string.

        Returns the explicitly set DSN if provided, otherwise constructs
        one from the individual connection parameters.
        """
        if self.dsn:
            return self.dsn
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @field_validator("dsn", mode="before")
    @classmethod
    def validate_dsn(cls, v: str | None) -> str | None:
        """Validate DSN format if provided."""
        if v is None or v == "":
            return None
        # Basic validation - pydantic PostgresDsn would be stricter
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("DSN must start with postgresql:// or postgres://")
        return v


class ProducerSettings(BaseSettings):
    """Trade producer configuration."""

    model_config = SettingsConfigDict(
        env_prefix="PRODUCER_",
        extra="ignore",
    )

    rate: int = Field(
        default=10,
        ge=1,
        le=10000,
        description="Events per second (normal rate)",
    )
    burst_enabled: bool = Field(
        default=True,
        description="Enable burst mode to simulate market volatility",
    )
    burst_multiplier: int = Field(
        default=5,
        ge=2,
        le=100,
        description="Rate multiplier during burst periods",
    )
    burst_duration: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Burst duration in seconds",
    )
    burst_interval: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Time between bursts in seconds",
    )

    # Retry settings (Fix #2, #8)
    buffer_retry_max: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum retry attempts for BufferError",
    )
    buffer_retry_backoff_base: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Base backoff delay in seconds for BufferError retry",
    )
    buffer_retry_backoff_max: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Maximum backoff delay in seconds",
    )
    buffer_retry_jitter: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Jitter factor (0-1) for backoff randomization",
    )
    kafka_produce_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for Kafka produce errors",
    )
    parking_queue_max_size: int = Field(
        default=1000,
        ge=10,
        le=100000,
        description="Maximum size of parking queue for failed messages",
    )


class ConsumerSettings(BaseSettings):
    """Streaming consumer configuration."""

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )

    window_duration_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Tumbling window duration in seconds",
    )
    late_event_grace_seconds: int = Field(
        default=30,
        ge=0,
        le=300,
        description="Grace period for late-arriving events",
    )
    db_batch_size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum batch size for database writes",
    )

    # Idle flush settings
    idle_flush_interval: int = Field(
        default=60,
        ge=10,
        le=600,
        description="Interval in seconds for flushing idle windows",
    )
    idle_flush_max_batch: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum windows to flush per idle flush cycle",
    )

    # Memory estimation
    empirical_bytes_per_window: int = Field(
        default=5000,
        ge=1000,
        le=100000,
        description="Empirical memory cost per window (measured with realistic workload)",
    )

    # Backpressure thresholds (configurable to tune for different workloads)
    backpressure_high_watermark: int = Field(
        default=1000,
        ge=100,
        le=50000,
        description="In-flight message count to trigger consumption pause",
    )
    backpressure_low_watermark: int = Field(
        default=100,
        ge=10,
        le=10000,
        description="In-flight message count to trigger consumption resume",
    )


class APISettings(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(
        env_prefix="API_",
        extra="ignore",
    )

    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins. Use ['*'] only in development.",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS requests",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v) -> list[str]:
        """Parse CORS origins from comma-separated string, JSON, or list."""
        if v is None:
            return ["http://localhost:3000", "http://localhost:8080"]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return list(v)


class SourceSettings(BaseSettings):
    """Base settings for data source connectors."""

    model_config = SettingsConfigDict(extra="ignore")

    enabled: bool = Field(default=False, description="Whether this source is enabled")
    name: str = Field(description="Unique name for this source")
    source_type: str = Field(description="Type of connector (websocket, sse, polling, etc.)")

    # Resilience settings
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0)
    circuit_breaker_enabled: bool = Field(default=True)
    circuit_breaker_threshold: int = Field(default=5, ge=1, le=50)
    circuit_breaker_timeout: int = Field(default=30, ge=5, le=300)

    def to_connector_config(self) -> dict:
        """Convert to connector configuration dict."""
        return {
            "name": self.name,
        }


class WebSocketSourceSettings(SourceSettings):
    """WebSocket source configuration (e.g., Finnhub)."""

    model_config = SettingsConfigDict(
        env_prefix="WS_",
        extra="ignore",
    )

    source_type: str = Field(default="websocket")
    url: str = Field(
        default="wss://ws.finnhub.io",
        description="WebSocket endpoint URL",
    )
    api_key: str = Field(
        default="",
        description="API key for authentication",
    )
    symbols: list[str] = Field(
        default=["AAPL", "GOOGL", "MSFT", "AMZN", "BINANCE:BTCUSDT"],
        description="Symbols to subscribe to",
    )
    ping_interval: int = Field(
        default=30,
        ge=10,
        le=120,
        description="Ping interval in seconds",
    )
    reconnect_delay: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Delay before reconnection attempt",
    )

    @field_validator("symbols", mode="before")
    @classmethod
    def parse_symbols(cls, v) -> list[str]:
        """Parse symbols from comma-separated string, JSON, or list."""
        if v is None:
            return ["AAPL", "GOOGL", "MSFT", "AMZN", "BINANCE:BTCUSDT"]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Try JSON parsing first (pydantic-settings may send JSON)
            v = v.strip()
            if v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # Fallback to comma-separated
            return [s.strip() for s in v.split(",") if s.strip()]
        return list(v)

    def to_connector_config(self) -> dict:
        """Convert to connector configuration dict."""
        return {
            "name": self.name,
            "url": self.url,
            "api_key": self.api_key,
            "symbols": self.symbols,
            "ping_interval": self.ping_interval,
            "reconnect_delay": self.reconnect_delay,
        }


class SSESourceSettings(SourceSettings):
    """SSE source configuration (e.g., DexPaprika)."""

    model_config = SettingsConfigDict(
        env_prefix="SSE_",
        extra="ignore",
    )

    source_type: str = Field(default="sse")
    url: str = Field(
        default="https://api.dexpaprika.com/sse/prices",
        description="SSE endpoint URL",
    )
    symbols: list[str] = Field(
        default=["BTC", "ETH", "SOL"],
        description="Crypto symbols to subscribe to",
    )
    timeout: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Connection timeout in seconds",
    )

    @field_validator("symbols", mode="before")
    @classmethod
    def parse_symbols(cls, v) -> list[str]:
        """Parse symbols from comma-separated string, JSON, or list."""
        if v is None:
            return ["BTC", "ETH", "SOL"]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Try JSON parsing first (pydantic-settings may send JSON)
            v = v.strip()
            if v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # Fallback to comma-separated
            return [s.strip() for s in v.split(",") if s.strip()]
        return list(v)

    def to_connector_config(self) -> dict:
        """Convert to connector configuration dict."""
        return {
            "name": self.name,
            "url": self.url,
            "symbols": self.symbols,
            "timeout": self.timeout,
        }


class PollingSourceSettings(SourceSettings):
    """Polling source configuration (e.g., ENTSO-E)."""

    model_config = SettingsConfigDict(
        env_prefix="POLLING_",
        extra="ignore",
    )

    source_type: str = Field(default="polling")
    url: str = Field(
        default="https://web-api.tp.entsoe.eu/api",
        description="REST API endpoint URL",
    )
    api_key: str = Field(
        default="",
        description="API key for authentication",
    )
    poll_interval: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Polling interval in seconds",
    )
    areas: list[str] = Field(
        default=["DE", "FR", "NL"],
        description="Energy market areas to poll",
    )

    @field_validator("areas", mode="before")
    @classmethod
    def parse_areas(cls, v) -> list[str]:
        """Parse areas from comma-separated string, JSON, or list."""
        if v is None:
            return ["DE", "FR", "NL"]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Try JSON parsing first (pydantic-settings may send JSON)
            v = v.strip()
            if v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # Fallback to comma-separated
            return [a.strip() for a in v.split(",") if a.strip()]
        return list(v)

    def to_connector_config(self) -> dict:
        """Convert to connector configuration dict."""
        return {
            "name": self.name,
            "url": self.url,
            "api_key": self.api_key,
            "poll_interval": self.poll_interval,
            "areas": self.areas,
        }


class WebhookSourceSettings(SourceSettings):
    """Webhook source configuration."""

    model_config = SettingsConfigDict(
        env_prefix="WEBHOOK_",
        extra="ignore",
    )

    source_type: str = Field(default="webhook")
    host: str = Field(
        default="0.0.0.0",
        description="Host to bind webhook server",
    )
    port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        description="Port for webhook server",
    )
    path: str = Field(
        default="/webhook/trades",
        description="URL path for webhook endpoint",
    )
    secret: str = Field(
        default="",
        description="Shared secret for webhook validation",
    )

    def to_connector_config(self) -> dict:
        """Convert to connector configuration dict."""
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "path": self.path,
            "secret": self.secret,
        }


class MicroBatchSourceSettings(SourceSettings):
    """Micro-batch source configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MICROBATCH_",
        extra="ignore",
    )

    source_type: str = Field(default="micro_batch")
    upstream_source: str | None = Field(
        default=None,
        description="Name of upstream source connector to wrap (e.g., 'finnhub'). "
                    "The upstream's events are buffered and flushed as micro-batches. "
                    "If None, operates in push mode via add_event().",
    )
    window_seconds: int = Field(
        default=10,
        ge=1,
        le=300,
        description="Window duration for micro-batching",
    )
    max_batch_size: int = Field(
        default=1000,
        ge=10,
        le=100000,
        description="Maximum events per batch",
    )

    def to_connector_config(self) -> dict:
        """Convert to connector configuration dict."""
        return {
            "name": self.name,
            "window_seconds": self.window_seconds,
            "max_batch_size": self.max_batch_size,
        }


class BatchSourceSettings(SourceSettings):
    """Batch file source configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BATCH_",
        extra="ignore",
    )

    source_type: str = Field(default="batch")
    directory: str = Field(
        default="/data/imports",
        description="Directory to watch for batch files",
    )
    file_pattern: str = Field(
        default="*.csv",
        description="Glob pattern for matching files",
    )
    poll_interval: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Interval for checking new files",
    )
    archive_directory: str | None = Field(
        default=None,
        description="Directory to move processed files",
    )
    checkpoint_file: str = Field(
        default="/data/.batch_checkpoint",
        description="File for tracking processed files",
    )

    def to_connector_config(self) -> dict:
        """Convert to connector configuration dict."""
        return {
            "name": self.name,
            "input_path": self.directory,
            "file_pattern": self.file_pattern,
            "poll_interval": self.poll_interval,
            "archive_path": self.archive_directory,
            "checkpoint_file": self.checkpoint_file,
        }


class IngestionSettings(BaseSettings):
    """Ingestion service configuration.

    Aggregates all data source configurations and ingestion-specific settings.

    Modes:
        - LOCAL: No ingestion service needed (use synthetic producer)
        - REALTIME: WebSocket (Finnhub), SSE (DexPaprika), Polling (ENTSO-E)
        - BATCH: CSV/Parquet file processing
        - HYBRID: Both real-time and batch sources
    """

    model_config = SettingsConfigDict(
        env_prefix="INGESTION_",
        extra="ignore",
    )

    # Ingestion mode
    mode: IngestionMode = Field(
        default=IngestionMode.LOCAL,
        description="Ingestion mode: local, realtime, batch, or hybrid",
    )

    # Metrics server
    metrics_port: int = Field(
        default=8003,
        ge=1024,
        le=65535,
        description="Port for Prometheus metrics endpoint",
    )
    metrics_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics collection",
    )

    # DLQ settings
    dlq_enabled: bool = Field(
        default=True,
        description="Enable dead letter queue for failed events",
    )

    # Pipeline settings
    dedup_cache_size: int = Field(
        default=50000,
        ge=1000,
        le=1000000,
        description="Size of deduplication cache",
    )
    validation_strict: bool = Field(
        default=True,
        description="Enable strict validation mode",
    )

    @property
    def websocket(self) -> WebSocketSourceSettings:
        """Get WebSocket source settings (loaded from WS_* env vars)."""
        return WebSocketSourceSettings(name="finnhub")

    @property
    def sse(self) -> SSESourceSettings:
        """Get SSE source settings (loaded from SSE_* env vars)."""
        return SSESourceSettings(name="dexpaprika")

    @property
    def polling(self) -> PollingSourceSettings:
        """Get Polling source settings (loaded from POLLING_* env vars)."""
        return PollingSourceSettings(name="entsoe")

    @property
    def webhook(self) -> WebhookSourceSettings:
        """Get Webhook source settings (loaded from WEBHOOK_* env vars)."""
        return WebhookSourceSettings(name="webhook")

    @property
    def micro_batch(self) -> MicroBatchSourceSettings:
        """Get Micro-batch source settings (loaded from MICROBATCH_* env vars)."""
        return MicroBatchSourceSettings(name="micro_batch")

    @property
    def batch(self) -> BatchSourceSettings:
        """Get Batch source settings (loaded from BATCH_* env vars)."""
        return BatchSourceSettings(name="batch")

    def get_enabled_sources(self) -> list[SourceSettings]:
        """Get list of enabled source configurations based on mode.

        Returns sources appropriate for the current ingestion mode:
        - LOCAL: Empty list (use synthetic producer instead)
        - REALTIME: WebSocket, SSE, Polling (if individually enabled)
        - BATCH: Batch file processor (if enabled)
        - HYBRID: All real-time + batch sources (if individually enabled)
        """
        if self.mode == IngestionMode.LOCAL:
            # Local mode uses synthetic producer, not ingestion service
            return []

        sources: list[SourceSettings] = []

        # Real-time sources (REALTIME or HYBRID mode)
        if self.mode in (IngestionMode.REALTIME, IngestionMode.HYBRID):
            if self.websocket.enabled:
                sources.append(self.websocket)
            if self.sse.enabled:
                sources.append(self.sse)
            if self.polling.enabled:
                sources.append(self.polling)
            if self.webhook.enabled:
                sources.append(self.webhook)

        # Batch sources (BATCH or HYBRID mode)
        if self.mode in (IngestionMode.BATCH, IngestionMode.HYBRID):
            if self.micro_batch.enabled:
                sources.append(self.micro_batch)
            if self.batch.enabled:
                sources.append(self.batch)

        return sources

    def is_ingestion_needed(self) -> bool:
        """Check if ingestion service should run.

        Returns False for LOCAL mode (uses synthetic producer).
        """
        return self.mode != IngestionMode.LOCAL


class Settings(BaseSettings):
    """Main application settings.

    Aggregates all configuration sections and provides application-wide settings.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        env_nested_delimiter="__",
    )

    # Nested configuration sections
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    producer: ProducerSettings = Field(default_factory=ProducerSettings)
    consumer: ConsumerSettings = Field(default_factory=ConsumerSettings)
    api: APISettings = Field(default_factory=APISettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)

    # Application-wide settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_json_format: bool = Field(
        default=False,
        description="Use JSON format for logs (recommended for production)",
    )
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Runtime environment",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    Uses lru_cache to ensure settings are loaded once and reused.
    This is the recommended way to access settings throughout the application.

    Returns:
        Settings: The application settings instance.
    """
    return Settings()
