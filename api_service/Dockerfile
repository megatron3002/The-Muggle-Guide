# ── Build stage ──
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ──
FROM python:3.11-slim

WORKDIR /app

# Security: non-root user
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/false appuser

COPY --from=builder /install /usr/local
COPY . .

RUN mkdir -p /app/shared/models && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--access-log", "--log-level", "info"]
