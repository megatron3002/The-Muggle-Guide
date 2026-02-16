"""Recommendation engine configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str = "development"
    model_storage_path: str = "/app/shared/models"
    model_storage_type: str = "s3"  # local | s3

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = "changeme"
    redis_url: Optional[str] = None

    aws_region: str = "us-east-1"
    aws_s3_bucket: str = "bookrec-models"
    aws_endpoint_url: Optional[str] = None  # LocalStack: http://localstack:4566

    log_level: str = "INFO"
    hybrid_alpha: float = 0.7  # Weight for collaborative vs content-based

    @property
    def redis_dsn(self) -> str:
        if self.redis_url:
            return self.redis_url
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
