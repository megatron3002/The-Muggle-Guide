FROM python:3.11-slim

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser -s /bin/false appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/shared/models && chown -R appuser:appuser /app

USER appuser

CMD ["celery", "-A", "app.celery_app:celery", "worker", "--loglevel=info", "--concurrency=2", "--max-tasks-per-child=50"]
