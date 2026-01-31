# Multi-Source Data Ingestion Service Dockerfile
# Multi-stage build for minimal, secure production image
#
# Design decisions:
# 1. Multi-stage build: Separate build and runtime stages
# 2. Minimal base image: python:3.12-slim for small footprint
# 3. Non-root user: Security best practice
# 4. No secrets in image: Configuration via environment variables

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
WORKDIR /build

# Copy only dependency files first (better layer caching)
COPY pyproject.toml README.md ./
COPY src/__init__.py ./src/

# Install dependencies (including extra ingestion dependencies)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    pip install --no-cache-dir httpx aiofiles aiohttp

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.12-slim AS runtime

# Security: Run as non-root user
RUN groupadd --gid 1000 trading && \
    useradd --uid 1000 --gid trading --shell /bin/bash --create-home trading

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=trading:trading src/ ./src/

# Create data directories
RUN mkdir -p /data/imports && chown -R trading:trading /data

# Switch to non-root user
USER trading

# Environment variables (override in docker-compose or k8s)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    LOG_LEVEL=INFO \
    KAFKA_BOOTSTRAP_SERVERS=localhost:9092 \
    KAFKA_TOPIC=trades \
    KAFKA_DLQ_TOPIC=trades-dlq \
    INGESTION_METRICS_PORT=8003 \
    INGESTION_METRICS_ENABLED=true

# Expose metrics port
EXPOSE 8003

# Health check via Prometheus metrics endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8003/metrics || exit 1

# Run the ingestion service
CMD ["python", "-m", "ingestion.main"]

# =============================================================================
# Labels for container metadata
# =============================================================================
LABEL org.opencontainers.image.title="Multi-Source Data Ingestion Service" \
      org.opencontainers.image.description="Ingests data from WebSocket, SSE, Polling, Webhook, Micro-batch, and Batch sources" \
      org.opencontainers.image.vendor="Energy Trading Platform" \
      org.opencontainers.image.source="https://github.com/example/energy-trading-platform"
