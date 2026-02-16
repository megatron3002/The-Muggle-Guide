"""
Redis-backed sliding window rate limiter (application level).

- 10 requests per minute per authenticated user
- Also enforces per-IP limits as fallback for unauthenticated routes

Uses Redis sorted sets for precise sliding window counting.
"""

from __future__ import annotations

import time

import redis.asyncio as redis
import structlog
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.config import get_settings

logger = structlog.get_logger()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        settings = get_settings()
        self.redis_client: redis.Redis | None = None
        self.per_user_limit = settings.rate_limit_per_user  # 10
        self.per_ip_limit = settings.rate_limit_per_ip  # 50
        self.window_seconds = settings.rate_limit_window_seconds  # 60
        self._redis_url = settings.redis_dsn

    async def _get_redis(self) -> redis.Redis:
        if self.redis_client is None:
            self.redis_client = redis.from_url(self._redis_url, decode_responses=True)
        return self.redis_client

    async def _check_rate_limit(self, key: str, limit: int) -> tuple[bool, int]:
        """
        Sliding window rate limiter using Redis sorted sets.
        Returns (allowed: bool, remaining: int).
        """
        try:
            r = await self._get_redis()
            now = time.time()
            window_start = now - self.window_seconds
            pipe = r.pipeline()

            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            # Count current entries
            pipe.zcard(key)
            # Add current request
            pipe.zadd(key, {f"{now}": now})
            # Set expiry on the key
            pipe.expire(key, self.window_seconds + 1)

            results = await pipe.execute()
            current_count = results[1]

            if current_count >= limit:
                return False, 0

            remaining = limit - current_count - 1
            return True, max(remaining, 0)

        except redis.RedisError:
            # If Redis is down, allow the request (fail open)
            logger.warning("rate_limiter_redis_error", key=key)
            return True, limit

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting for health checks and metrics
        if request.url.path in ("/health", "/metrics", "/ready"):
            return await call_next(request)

        # Get client IP
        client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")

        # Check per-IP rate limit
        ip_key = f"ratelimit:ip:{client_ip}"
        ip_allowed, ip_remaining = await self._check_rate_limit(ip_key, self.per_ip_limit)

        if not ip_allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests from this IP",
                    "retry_after": self.window_seconds,
                },
                headers={"Retry-After": str(self.window_seconds)},
            )

        # Check per-user rate limit if authenticated
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            from app.auth.jwt_handler import verify_token

            token = auth_header.split(" ", 1)[1]
            payload = verify_token(token)
            if payload and payload.get("type") == "access":
                user_id = payload["sub"]
                user_key = f"ratelimit:user:{user_id}"
                user_allowed, user_remaining = await self._check_rate_limit(user_key, self.per_user_limit)
                if not user_allowed:
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "detail": "Too many requests — user rate limit exceeded",
                            "retry_after": self.window_seconds,
                        },
                        headers={"Retry-After": str(self.window_seconds)},
                    )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining-IP"] = str(ip_remaining)
        return response
