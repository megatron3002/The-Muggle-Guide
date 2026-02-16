"""
Recommendation engine internal API — called by the API service.

Endpoints:
- POST /recommend/top — top-N for a user
- POST /recommend/similar — similar books to a given book
- POST /reload — reload model artifacts
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter
from prometheus_client import Histogram
from pydantic import BaseModel, Field

from app.cold_start import cold_start_handler
from app.models.hybrid import hybrid_recommender

logger = structlog.get_logger()
router = APIRouter()

INFERENCE_LATENCY = Histogram(
    "recommendation_inference_seconds",
    "Time spent computing recommendations",
    ["strategy"],
)


class TopRequest(BaseModel):
    user_id: int
    n: int = Field(10, ge=1, le=50)
    interactions: list[dict] = []  # [{book_id, interaction_type, rating}]


class SimilarRequest(BaseModel):
    book_id: int
    n: int = Field(10, ge=1, le=50)


@router.post("/recommend/top")
async def recommend_top(request: TopRequest):
    """Generate top-N recommendations for a user."""
    start = time.time()

    # Extract liked book IDs from interactions
    liked_book_ids = [
        i["book_id"] for i in request.interactions if i.get("interaction_type") in ("like", "rate", "purchase")
    ]

    # Check cold start
    if not liked_book_ids:
        results = cold_start_handler.get_popular_recommendations(request.n)
        strategy = "cold_start"
        if not results:
            # Ultimate fallback — no models or data loaded
            return {
                "user_id": request.user_id,
                "recommendations": [],
                "strategy": "none",
            }
    else:
        results, strategy = hybrid_recommender.get_recommendations(
            user_id=request.user_id,
            liked_book_ids=liked_book_ids,
            n=request.n,
        )

    latency = time.time() - start
    INFERENCE_LATENCY.labels(strategy=strategy).observe(latency)
    logger.info(
        "recommendation_generated",
        user_id=request.user_id,
        n=len(results),
        strategy=strategy,
        latency_ms=round(latency * 1000, 2),
    )

    return {
        "user_id": request.user_id,
        "recommendations": results,
        "strategy": strategy,
    }


@router.post("/recommend/similar")
async def recommend_similar(request: SimilarRequest):
    """Find similar books."""
    start = time.time()

    results, strategy = hybrid_recommender.get_similar_books(book_id=request.book_id, n=request.n)

    if not results:
        # Try cold start content-based fallback
        results = cold_start_handler.get_new_book_neighbors(request.book_id, request.n)
        strategy = "content_fallback"

    latency = time.time() - start
    INFERENCE_LATENCY.labels(strategy=strategy).observe(latency)

    return {
        "book_id": request.book_id,
        "similar_books": results,
        "strategy": strategy,
    }


@router.post("/reload")
async def reload_models():
    """Trigger model reload from disk (called after training completes)."""
    from app.model_store import model_store
    from app.models.collaborative import collab_recommender
    from app.models.content_based import content_recommender

    model_store.reload()
    content_loaded = content_recommender.load()
    collab_loaded = collab_recommender.load()
    cold_start_handler.load()

    return {
        "status": "reloaded",
        "content_model": "loaded" if content_loaded else "not_available",
        "collab_model": "loaded" if collab_loaded else "not_available",
    }
