"""
Application configuration — loads from .env (dev) or AWS Secrets Manager (prod).
No secrets are ever hardcoded.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Environment ──
    environment: str = "development"

    # ── Postgres ──
    postgres_user: str = "bookrec_user"
    postgres_password: str = "changeme"
    postgres_db: str = "bookrec"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    database_url: Optional[str] = None

    # ── Redis ──
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = "changeme"
    redis_url: Optional[str] = None

    # ── JWT ──
    jwt_secret_key: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── Rate Limiting ──
    rate_limit_per_user: int = 10
    rate_limit_per_ip: int = 50
    rate_limit_window_seconds: int = 60

    # ── Internal services ──
    recommendation_engine_url: str = "http://recommendation_engine:8001"

    # ── Celery ──
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # ── Model Storage ──
    model_storage_path: str = "/app/shared/models"
    model_storage_type: str = "s3"  # local | s3

    # ── AWS ──
    aws_region: str = "us-east-1"
    aws_s3_bucket: str = "bookrec-models"
    aws_secrets_manager_secret_name: str = "bookrec/production"
    aws_endpoint_url: Optional[str] = None  # LocalStack: http://localstack:4566

    # ── Monitoring ──
    enable_metrics: bool = True
    log_level: str = "INFO"
    log_format: str = "json"

    # ── CORS ──
    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    @property
    def database_dsn(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_dsn(self) -> str:
        return self.database_dsn.replace("+asyncpg", "")

    @property
    def redis_dsn(self) -> str:
        if self.redis_url:
            return self.redis_url
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def _fetch_aws_secrets(secret_name: str, region: str, endpoint_url: Optional[str] = None) -> dict:
    """Fetch secrets from AWS Secrets Manager.
    Uses LocalStack endpoint in dev, real AWS in production."""
    import boto3

    kwargs = {"region_name": region}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    client = boto3.client("secretsmanager", **kwargs)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()

    # Overlay secrets from AWS Secrets Manager
    # Works in both development (LocalStack) and production (real AWS)
    if settings.aws_endpoint_url or settings.environment == "production":
        try:
            secrets = _fetch_aws_secrets(
                settings.aws_secrets_manager_secret_name,
                settings.aws_region,
                settings.aws_endpoint_url,
            )
            for key, value in secrets.items():
                if hasattr(settings, key.lower()):
                    setattr(settings, key.lower(), value)
        except Exception:
            import structlog

            logger = structlog.get_logger()
            logger.error("Failed to fetch AWS secrets — falling back to env vars")

    return settings
