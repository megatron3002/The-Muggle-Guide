"""Model store for the training pipeline (save side).
Supports LocalStack in development and real AWS in production.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

BASE_PATH = Path(settings.model_storage_path)
BASE_PATH.mkdir(parents=True, exist_ok=True)


def _get_s3_client():
    """Create an S3 client, routing to LocalStack when aws_endpoint_url is set."""
    import boto3

    kwargs = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("s3", **kwargs)


def save_artifact(name: str, obj, version: str = "latest") -> str:
    """Pickle and save a model artifact."""
    path = BASE_PATH / f"{name}_{version}.pkl"
    with open(path, "wb") as f:
        pickle.dump(obj, f)
    logger.info("artifact_saved", name=name, path=str(path))

    # Upload to S3 (LocalStack in dev, real AWS in prod)
    if settings.model_storage_type == "s3":
        _upload_to_s3(path, f"models/{name}_{version}.pkl")

    return str(path)


def save_metadata(metadata: dict) -> None:
    """Save training metadata."""
    path = BASE_PATH / "metadata.json"
    with open(path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    logger.info("metadata_saved", path=str(path))


def _upload_to_s3(local_path: Path, s3_key: str) -> None:
    try:
        s3 = _get_s3_client()
        s3.upload_file(str(local_path), settings.aws_s3_bucket, s3_key)
        logger.info("uploaded_to_s3", key=s3_key, endpoint=settings.aws_endpoint_url or "aws")
    except Exception as e:
        logger.error("s3_upload_error", error=str(e))
