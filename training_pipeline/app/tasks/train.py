"""
Main training task — orchestrates the full model retraining pipeline.

Steps:
1. Load data from PostgreSQL
2. Train content-based model (TF-IDF)
3. Train collaborative model (ALS)
4. Build popularity data for cold start
5. Evaluate models
6. Save metadata
7. Signal recommendation engine to reload
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
import structlog

from app.celery_app import celery
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


@celery.task(
    name="app.tasks.train.retrain_models",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def retrain_models(self):
    """Full model retraining pipeline."""
    task_id = self.request.id
    start_time = time.time()

    logger.info("retrain_started", task_id=task_id)

    try:
        # Step 1: Load data
        from app.pipeline.data_loader import load_books, load_interactions

        logger.info("step_1_loading_data")
        books_df = load_books()
        interactions_df = load_interactions()

        if books_df.empty:
            logger.error("no_books_in_database")
            return {"status": "failed", "reason": "no books in database"}

        # Step 2: Train content-based model
        from app.pipeline.content_trainer import train_content_model

        logger.info("step_2_training_content_model")
        content_metrics = train_content_model(books_df)

        # Step 3: Train collaborative model
        from app.pipeline.collab_trainer import train_collab_model

        logger.info("step_3_training_collab_model")
        collab_metrics = train_collab_model(interactions_df, books_df)

        # Step 4: Build popularity data for cold start
        logger.info("step_4_building_popularity_data")
        popularity_data = _build_popularity_data(books_df, interactions_df)

        from app.pipeline.model_store import save_artifact, save_metadata

        save_artifact("popularity_data", popularity_data)

        # Step 5: Save metadata
        training_duration = time.time() - start_time
        model_version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        metadata = {
            "model_version": model_version,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_duration_seconds": round(training_duration, 2),
            "content_metrics": content_metrics,
            "collab_metrics": collab_metrics,
            "data_stats": {
                "n_books": len(books_df),
                "n_interactions": len(interactions_df),
            },
        }
        save_metadata(metadata)

        # Step 6: Signal recommendation engine to reload
        logger.info("step_6_signaling_reload")
        _signal_reload()

        # Step 7: Update Redis status
        _update_status(task_id, model_version, metadata)

        logger.info(
            "retrain_completed",
            task_id=task_id,
            model_version=model_version,
            duration=round(training_duration, 2),
        )

        return {
            "status": "completed",
            "model_version": model_version,
            "duration_seconds": round(training_duration, 2),
            "metrics": metadata,
        }

    except Exception as exc:
        logger.error("retrain_failed", task_id=task_id, error=str(exc))
        raise self.retry(exc=exc)


def _build_popularity_data(books_df, interactions_df) -> dict:
    """Build popularity scores from interaction counts and ratings."""
    if interactions_df.empty:
        # Fallback to avg_rating
        popular = books_df.nlargest(50, "avg_rating")
    else:
        # Count interactions per book
        interaction_counts = interactions_df.groupby("book_id").size().reset_index(name="count")
        merged = books_df.merge(interaction_counts, left_on="id", right_on="book_id", how="left")
        merged["count"] = merged["count"].fillna(0)
        # Score = normalized count * 0.6 + normalized rating * 0.4
        max_count = merged["count"].max() if merged["count"].max() > 0 else 1
        max_rating = merged["avg_rating"].max() if merged["avg_rating"].max() > 0 else 1
        merged["pop_score"] = (merged["count"] / max_count) * 0.6 + (merged["avg_rating"] / max_rating) * 0.4
        popular = merged.nlargest(50, "pop_score")

    popular_books = []
    for _, row in popular.iterrows():
        popular_books.append(
            {
                "book_id": int(row["id"]),
                "title": row["title"],
                "author": row["author"],
                "genre": row["genre"],
                "score": float(row.get("pop_score", row.get("avg_rating", 0))),
            }
        )

    return {"popular_books": popular_books}


def _signal_reload():
    """Tell the recommendation engine to reload its models."""
    try:
        resp = httpx.post(f"{settings.recommendation_engine_url}/reload", timeout=10)
        logger.info("reload_signal_sent", status=resp.status_code)
    except Exception as e:
        logger.warning("reload_signal_failed", error=str(e))


def _update_status(task_id: str, model_version: str, metadata: dict):
    """Update training status in Redis."""
    try:
        import redis

        r = redis.from_url(settings.redis_dsn)
        import json

        r.setex(
            "model:retrain:latest",
            86400,
            json.dumps(
                {
                    "task_id": task_id,
                    "status": "completed",
                    "model_version": model_version,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "metrics": metadata,
                },
                default=str,
            ),
        )
    except Exception as e:
        logger.warning("redis_status_update_failed", error=str(e))
