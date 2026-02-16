"""Training pipeline configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str = "development"

    postgres_user: str = "bookrec_user"
    postgres_password: str = "changeme"
    postgres_db: str = "bookrec"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = "changeme"

    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    model_storage_path: str = "/app/shared/models"
    model_storage_type: str = "s3"  # local | s3

    aws_region: str = "us-east-1"
    aws_s3_bucket: str = "bookrec-models"
    aws_endpoint_url: Optional[str] = None  # LocalStack: http://localstack:4566

    recommendation_engine_url: str = "http://recommendation_engine:8001"

    # Hyperparameters
    als_factors: int = 64
    als_iterations: int = 30
    als_regularization: float = 0.1
    tfidf_max_features: int = 5000

    @property
    def database_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_dsn(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
