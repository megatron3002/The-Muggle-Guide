"""HTTP client for calling the internal Recommendation Engine service with circuit breaker and retry."""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from circuitbreaker import circuit
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=settings.recommendation_engine_url,
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
    return _client


@circuit(failure_threshold=5, recovery_timeout=30)
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
async def get_top_recommendations(user_id: int, n: int = 10, interactions: list | None = None) -> dict[str, Any]:
    """Call recommendation engine for top-N recommendations."""
    client = await _get_client()
    response = await client.post(
        "/recommend/top",
        json={"user_id": user_id, "n": n, "interactions": interactions or []},
    )
    response.raise_for_status()
    return response.json()


@circuit(failure_threshold=5, recovery_timeout=30)
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
async def get_similar_books(book_id: int, n: int = 10) -> dict[str, Any]:
    """Call recommendation engine for similar books."""
    client = await _get_client()
    response = await client.post(
        "/recommend/similar",
        json={"book_id": book_id, "n": n},
    )
    response.raise_for_status()
    return response.json()


async def close_client() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None
