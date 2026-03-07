FROM python:3.13-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

# --- runtime ---
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY src/ src/
COPY simulation/ simulation/

EXPOSE 8020

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8020"]
