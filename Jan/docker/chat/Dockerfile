FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    gradio>=4.0.0 \
    httpx>=0.25.0 \
    psycopg[binary]>=3.1.0 \
    pandas>=2.1.0

# Copy source code
COPY src/chat /app/src/chat

ENV PYTHONPATH=/app

EXPOSE 7860

CMD ["python", "-m", "src.chat.app"]
