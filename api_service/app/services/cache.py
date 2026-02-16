"""Redis cache helper — get/set/invalidate with JSON serialization."""

from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as redis
import structlog

from app.config import get_settings

logger = structlog.get_logger()

_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.redis_dsn, decode_responses=True)
    return _redis_client


async def get_cached(key: str) -> Optional[Any]:
    """Get a cached value by key."""
    try:
        r = await get_redis()
        value = await r.get(key)
        if value:
            return json.loads(value)
    except redis.RedisError:
        logger.warning("cache_get_error", key=key)
    return None


async def set_cached(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """Set a cached value with TTL (default 5 minutes)."""
    try:
        r = await get_redis()
        await r.setex(key, ttl_seconds, json.dumps(value, default=str))
    except redis.RedisError:
        logger.warning("cache_set_error", key=key)


async def invalidate(pattern: str) -> None:
    """Invalidate all cache keys matching a pattern."""
    try:
        r = await get_redis()
        async for key in r.scan_iter(match=pattern):
            await r.delete(key)
    except redis.RedisError:
        logger.warning("cache_invalidate_error", pattern=pattern)
