"""
Model artifact store — load and save model artifacts from local filesystem or S3.
Supports LocalStack in development and real AWS in production via aws_endpoint_url.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, Optional

import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


def _get_s3_client():
    """Create an S3 client, routing to LocalStack when aws_endpoint_url is set."""
    import boto3

    kwargs = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return boto3.client("s3", **kwargs)


class ModelStore:
    """Manages loading and saving of trained model artifacts."""

    def __init__(self):
        self.base_path = Path(settings.model_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Any] = {}

    def save_artifact(self, name: str, obj: Any, version: str = "latest") -> str:
        """Save a model artifact (pickle)."""
        path = self.base_path / f"{name}_{version}.pkl"
        with open(path, "wb") as f:
            pickle.dump(obj, f)
        logger.info("model_artifact_saved", name=name, version=version, path=str(path))

        # Also upload to S3 (LocalStack in dev, real AWS in prod)
        if settings.model_storage_type == "s3":
            self._upload_to_s3(path, f"models/{name}_{version}.pkl")

        return str(path)

    def load_artifact(self, name: str, version: str = "latest") -> Optional[Any]:
        """Load a model artifact. Returns None if not found."""
        cache_key = f"{name}_{version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.base_path / f"{name}_{version}.pkl"
        if not path.exists():
            # Try downloading from S3
            if settings.model_storage_type == "s3":
                success = self._download_from_s3(f"models/{name}_{version}.pkl", path)
                if not success:
                    logger.warning("model_artifact_not_found", name=name, version=version)
                    return None
            else:
                logger.warning("model_artifact_not_found", name=name, version=version)
                return None

        with open(path, "rb") as f:
            obj = pickle.load(f)

        self._cache[cache_key] = obj
        logger.info("model_artifact_loaded", name=name, version=version)
        return obj

    def save_metadata(self, metadata: dict) -> None:
        """Save model metadata as JSON."""
        path = self.base_path / "metadata.json"
        with open(path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

    def load_metadata(self) -> Optional[dict]:
        """Load model metadata."""
        path = self.base_path / "metadata.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def reload(self) -> None:
        """Clear cache to force reload on next access."""
        self._cache.clear()
        logger.info("model_cache_cleared")

    def _upload_to_s3(self, local_path: Path, s3_key: str) -> None:
        try:
            s3 = _get_s3_client()
            s3.upload_file(str(local_path), settings.aws_s3_bucket, s3_key)
            logger.info("model_uploaded_to_s3", key=s3_key, endpoint=settings.aws_endpoint_url or "aws")
        except Exception as e:
            logger.error("s3_upload_error", error=str(e))

    def _download_from_s3(self, s3_key: str, local_path: Path) -> bool:
        try:
            s3 = _get_s3_client()
            s3.download_file(settings.aws_s3_bucket, s3_key, str(local_path))
            logger.info("model_downloaded_from_s3", key=s3_key, endpoint=settings.aws_endpoint_url or "aws")
            return True
        except Exception as e:
            logger.error("s3_download_error", error=str(e))
            return False


# Singleton
model_store = ModelStore()
