FROM python:3.13-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY pyproject.toml .
COPY ../cysec-shared /cysec-shared
RUN pip install --no-cache-dir /cysec-shared && \
    pip install --no-cache-dir .

# Copy source
COPY src/ src/

# API port
EXPOSE 8000

# Streamlit port
EXPOSE 8501

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
