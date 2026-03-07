# ── Base ──────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS base

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .

# Install the shared package first (path dependency resolved at build time)
COPY ../cysec-shared /cysec-shared

# Install all dependencies
RUN uv pip install --system --no-cache -e ".[dev]" \
    --find-links /cysec-shared

COPY src/ ./src/

# ── API ───────────────────────────────────────────────────────────────────────
FROM base AS api

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Dashboard ─────────────────────────────────────────────────────────────────
FROM base AS dashboard

EXPOSE 8501

CMD ["streamlit", "run", "src/dashboard/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
