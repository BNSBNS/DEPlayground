FROM python:3.13-slim AS builder

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM python:3.13-slim AS runtime

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ src/
COPY simulation/ simulation/

EXPOSE 8030

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8030"]
