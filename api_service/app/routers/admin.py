"""Admin routes — model retraining and status (admin only)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_admin
from app.schemas.recommendation import ModelStatusResponse, RetrainResponse
from app.services.cache import get_cached, set_cached

logger = structlog.get_logger()
router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/retrain", response_model=RetrainResponse, status_code=202)
async def trigger_retrain(
    _admin: dict = Depends(require_admin),
):
    """
    Trigger model retraining (admin only).
    Dispatches an async Celery task and returns immediately.
    """
    try:
        from celery import Celery

        from app.config import get_settings

        settings = get_settings()
        celery_app = Celery(broker=settings.celery_broker_url)
        result = celery_app.send_task("app.tasks.train.retrain_models")
        task_id = result.id

        # Store task status
        await set_cached(
            "model:retrain:latest",
            {
                "task_id": task_id,
                "status": "queued",
                "triggered_at": datetime.now(timezone.utc).isoformat(),
                "triggered_by": _admin["user_id"],
            },
            ttl_seconds=86400,
        )

        logger.info("retrain_triggered", task_id=task_id, admin_id=_admin["user_id"])

        return RetrainResponse(
            task_id=task_id,
            status="queued",
            message="Model retraining task has been queued",
        )
    except Exception as e:
        logger.error("retrain_trigger_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to trigger retraining")


@router.get("/model-status", response_model=ModelStatusResponse)
async def model_status(
    _admin: dict = Depends(require_admin),
):
    """Get the latest model training status and metrics."""
    cached = await get_cached("model:retrain:latest")
    if cached:
        return ModelStatusResponse(
            status=cached.get("status", "unknown"),
            last_trained=cached.get("completed_at"),
            model_version=cached.get("model_version"),
            metrics=cached.get("metrics"),
        )

    return ModelStatusResponse(
        status="no_training_history",
        last_trained=None,
        model_version=None,
        metrics=None,
    )
