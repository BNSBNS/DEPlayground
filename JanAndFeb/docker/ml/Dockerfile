# ML Forecasting Dockerfile
# Runs `trade-ml train` / `trade-ml schedule` — the only containers in the
# stack that carry torch / lightgbm / statsmodels. The core trading images
# stay lean because this one lives under a separate compose profile.
#
# Design decisions mirror docker/consumer/Dockerfile:
#   1. Multi-stage build: separate builder and runtime stages
#   2. Installs `.[ml]` optional extras (heavy ML stack)
#   3. Non-root user (security best practice)
#   4. Process-based healthcheck (no HTTP endpoint on the worker)

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.12-slim AS builder

# Build deps: gcc/libpq for psycopg, plus the tools the ML wheels occasionally
# need to build source distributions on linux/arm64.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Copy only dependency files first for better layer caching.
COPY pyproject.toml README.md ./
COPY src/__init__.py ./src/

# Install core deps + [ml] extras (torch, lightgbm, statsmodels, apscheduler).
# We force torch's CPU-only wheel to avoid pulling in ~2 GB of CUDA libraries.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        ".[ml]"

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.12-slim AS runtime

# Security: run as non-root
RUN groupadd --gid 1000 trading && \
    useradd --uid 1000 --gid trading --shell /bin/bash --create-home trading

# Runtime deps only:
#   libpq5     - psycopg
#   libgomp1   - LightGBM / torch OpenMP runtime
#   curl       - diagnostics
#   procps     - pgrep for the healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy application code
COPY --chown=trading:trading src/ ./src/

# Writable location for FilesystemModelStore — mounted as a volume in compose.
RUN mkdir -p /app/data/ml_models && chown -R trading:trading /app/data

USER trading

# 12-factor env. Overridden by compose.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO \
    ML_MODEL_STORE_PATH=/app/data/ml_models

# The scheduler is a long-running loop; the trainer is one-shot. Both go
# through `trade-ml`, so the healthcheck just verifies the Python process.
HEALTHCHECK --interval=60s --timeout=10s --start-period=15s --retries=3 \
    CMD pgrep -f "trade-ml" || exit 1

# Default command: long-running retrain scheduler. The one-shot trainer
# service overrides this with `command: ["trade-ml", "train", ...]`.
CMD ["trade-ml", "schedule"]

# =============================================================================
# Labels
# =============================================================================
LABEL org.opencontainers.image.title="Trade ML Forecaster" \
      org.opencontainers.image.description="Classical, gradient, and deep-learning forecasters for energy trades" \
      org.opencontainers.image.vendor="Energy Trading Platform" \
      org.opencontainers.image.source="https://github.com/example/energy-trading-platform"
