# Streaming API Dockerfile
# FastAPI application for REST and WebSocket endpoints
#
# Design decisions:
# 1. Multi-stage build: Separate build and runtime stages
# 2. Minimal base image: python:3.12-slim for small footprint
# 3. Non-root user: Security best practice
# 4. Health check endpoint for Kubernetes probes

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

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

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

# Switch to non-root user
USER trading

# Environment variables (override in docker-compose or k8s)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO \
    KAFKA_BOOTSTRAP_SERVERS=localhost:9092 \
    KAFKA_TOPIC=trades \
    POSTGRES_HOST=localhost \
    POSTGRES_PORT=5432 \
    POSTGRES_USER=trading \
    POSTGRES_PASSWORD=trading \
    POSTGRES_DB=trades

# Expose API port
EXPOSE 8000

# Health check using the API health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the API server
CMD ["python", "-m", "src.api.main"]

# =============================================================================
# Labels for container metadata
# =============================================================================
LABEL org.opencontainers.image.title="Trade Streaming API" \
      org.opencontainers.image.description="FastAPI REST and WebSocket API for trade data" \
      org.opencontainers.image.vendor="Energy Trading Platform" \
      org.opencontainers.image.source="https://github.com/example/energy-trading-platform"
