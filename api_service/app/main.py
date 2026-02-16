"""
FastAPI application factory — the main entrypoint for the API service.

Features:
- CORS restrictions
- Redis rate limiting middleware
- Prometheus metrics endpoint
- Structured JSON logging
- Health / readiness / liveness probes
- Graceful shutdown
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest
from sqlalchemy import text

from app.config import get_settings
from app.logging_config import setup_logging
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.routers import admin, auth, books, interactions, recommendations

settings = get_settings()
setup_logging(settings.log_level, settings.log_format)
logger = structlog.get_logger()

# ── Prometheus metrics ──
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)
INFERENCE_LATENCY = Histogram(
    "recommendation_inference_seconds",
    "Recommendation inference latency",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and graceful shutdown."""
    logger.info("api_service_starting", environment=settings.environment)

    # Run DB table creation on first start (dev convenience)
    if settings.environment == "development":
        from app.database import Base, engine
        # Import all models so Base.metadata has them registered
        from app.models import user, book, interaction  # noqa: F401

        async with engine.begin() as conn:
            # Create PostgreSQL enum types FIRST (asyncpg requires this)
            await conn.execute(text(
                "DO $$ BEGIN "
                "CREATE TYPE userrole AS ENUM ('user', 'admin'); "
                "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
            ))
            await conn.execute(text(
                "DO $$ BEGIN "
                "CREATE TYPE interactiontype AS ENUM ('view', 'like', 'rate', 'purchase', 'bookmark'); "
                "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
            ))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_tables_created")

    yield

    # Graceful shutdown
    logger.info("api_service_shutting_down")
    from app.services.recommendation_client import close_client
    await close_client()


app = FastAPI(
    title="Book Recommendation System",
    description="Production-ready book recommendation API with hybrid ML models",
    version="1.0.0",
    root_path="/api",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting ──
app.add_middleware(RateLimiterMiddleware)


# ── Request metrics middleware ──
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    endpoint = request.url.path
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=endpoint,
    ).observe(duration)

    return response


# ── Routers ──
app.include_router(auth.router)
app.include_router(books.router)
app.include_router(interactions.router)
app.include_router(recommendations.router)
app.include_router(admin.router)


# ── Health / Readiness / Liveness ──
@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "service": "api"}


@app.get("/ready", tags=["Health"])
async def readiness():
    """Readiness probe — checks DB and Redis connectivity."""
    checks = {}
    try:
        from app.database import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        from app.services.cache import get_redis
        r = await get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )


@app.get("/live", tags=["Health"])
async def liveness():
    return {"status": "alive"}


# ── Prometheus metrics endpoint ──
@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    from starlette.responses import Response
    return Response(content=generate_latest(), media_type="text/plain")

