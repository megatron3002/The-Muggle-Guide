"""
Recommendation Engine — FastAPI app.

Internal service (not publicly exposed). Serves ML predictions.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_client import generate_latest

from app.cold_start import cold_start_handler
from app.config import get_settings
from app.models.collaborative import collab_recommender
from app.models.content_based import content_recommender
from app.routers import recommend

settings = get_settings()
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models at startup."""
    logger.info("recommendation_engine_starting")

    content_recommender.load()
    collab_recommender.load()
    cold_start_handler.load()

    logger.info(
        "models_loaded",
        content=content_recommender.is_loaded,
        collab=collab_recommender.is_loaded,
        cold_start=cold_start_handler._loaded,
    )

    yield

    logger.info("recommendation_engine_shutting_down")


app = FastAPI(
    title="Book Recommendation Engine",
    description="Internal ML recommendation service",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.include_router(recommend.router)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "recommendation_engine",
        "models": {
            "content_based": content_recommender.is_loaded,
            "collaborative": collab_recommender.is_loaded,
            "cold_start": cold_start_handler._loaded,
        },
    }


@app.get("/metrics")
async def metrics():
    from starlette.responses import Response
    return Response(content=generate_latest(), media_type="text/plain")
