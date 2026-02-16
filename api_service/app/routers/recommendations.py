"""Recommendation endpoints — top-N and similar books with Redis caching."""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.services.cache import get_cached, set_cached
from app.services.recommendation_client import get_similar_books, get_top_recommendations

logger = structlog.get_logger()
router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/top")
async def top_recommendations(
    n: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """
    Get top-N personalized recommendations for the current user.
    Results are cached in Redis for 5 minutes.
    """
    user_id = current_user["user_id"]
    cache_key = f"rec:user:{user_id}:top:{n}"

    # Check cache
    cached = await get_cached(cache_key)
    if cached:
        logger.info("recommendation_cache_hit", user_id=user_id)
        return cached

    # Call recommendation engine
    start_time = time.time()
    try:
        result = await get_top_recommendations(user_id=user_id, n=n)
    except Exception as e:
        logger.error("recommendation_engine_error", error=str(e), user_id=user_id)
        raise HTTPException(status_code=503, detail="Recommendation service unavailable")

    latency_ms = (time.time() - start_time) * 1000
    logger.info("recommendation_served", user_id=user_id, n=n, latency_ms=round(latency_ms, 2))

    # Cache result
    await set_cached(cache_key, result, ttl_seconds=300)
    return result


@router.get("/similar/{book_id}")
async def similar_books(
    book_id: int,
    n: int = Query(10, ge=1, le=50),
    _user: dict = Depends(get_current_user),
):
    """
    Get N books similar to the given book_id.
    Results are cached in Redis for 10 minutes.
    """
    cache_key = f"rec:similar:{book_id}:{n}"

    cached = await get_cached(cache_key)
    if cached:
        return cached

    start_time = time.time()
    try:
        result = await get_similar_books(book_id=book_id, n=n)
    except Exception as e:
        logger.error("similar_books_error", error=str(e), book_id=book_id)
        raise HTTPException(status_code=503, detail="Recommendation service unavailable")

    latency_ms = (time.time() - start_time) * 1000
    logger.info("similar_books_served", book_id=book_id, n=n, latency_ms=round(latency_ms, 2))

    await set_cached(cache_key, result, ttl_seconds=600)
    return result
