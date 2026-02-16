"""
Collaborative filtering trainer — ALS matrix factorization via `implicit`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from implicit.als import AlternatingLeastSquares
from scipy.sparse import coo_matrix

from app.config import get_settings
from app.pipeline.model_store import save_artifact

logger = structlog.get_logger()
settings = get_settings()


def train_collab_model(
    interactions_df: pd.DataFrame,
    books_df: pd.DataFrame,
) -> dict:
    """
    Train ALS collaborative filtering model:
    1. Build user-item interaction matrix
    2. Train ALS model
    3. Save model and mappings
    """
    if interactions_df.empty:
        logger.warning("no_interactions_for_collab_training")
        return {"status": "skipped", "reason": "no interactions"}

    logger.info("training_collab_model", n_interactions=len(interactions_df))

    # Create interaction weights
    # Weight by interaction type: view=1, like=2, bookmark=2, rate=rating, purchase=5
    weight_map = {"view": 1.0, "like": 2.0, "bookmark": 2.0, "purchase": 5.0, "rate": 3.0}
    interactions_df = interactions_df.copy()
    interactions_df["weight"] = interactions_df["interaction_type"].map(weight_map).fillna(1.0)

    # For rated interactions, use the rating as additional weight
    rated_mask = interactions_df["rating"].notna()
    interactions_df.loc[rated_mask, "weight"] = interactions_df.loc[rated_mask, "rating"]

    # Build user/item ID maps
    unique_users = sorted(interactions_df["user_id"].unique())
    unique_items = sorted(interactions_df["book_id"].unique())

    user_id_map = {uid: idx for idx, uid in enumerate(unique_users)}
    item_id_map = {iid: idx for idx, iid in enumerate(unique_items)}

    # Build sparse user-item matrix
    rows = interactions_df["user_id"].map(user_id_map).values
    cols = interactions_df["book_id"].map(item_id_map).values
    weights = interactions_df["weight"].values.astype(np.float32)

    n_users = len(unique_users)
    n_items = len(unique_items)

    user_item_matrix = coo_matrix((weights, (rows, cols)), shape=(n_users, n_items)).tocsr()

    # Train ALS
    model = AlternatingLeastSquares(
        factors=settings.als_factors,
        iterations=settings.als_iterations,
        regularization=settings.als_regularization,
        random_state=42,
    )
    model.fit(user_item_matrix)

    # Build book metadata for recommendations
    book_metadata = {}
    for _, row in books_df.iterrows():
        book_metadata[row["id"]] = {
            "title": row["title"],
            "author": row["author"],
            "genre": row["genre"],
        }

    # Save artifacts
    save_artifact("collab_als_model", model)
    save_artifact("collab_user_item_matrix", user_item_matrix)
    save_artifact(
        "collab_mappings",
        {
            "user_id_map": user_id_map,
            "item_id_map": item_id_map,
            "book_metadata": book_metadata,
        },
    )

    logger.info(
        "collab_model_trained",
        n_users=n_users,
        n_items=n_items,
        factors=settings.als_factors,
    )

    return {
        "n_users": n_users,
        "n_items": n_items,
        "n_interactions": len(interactions_df),
        "factors": settings.als_factors,
        "iterations": settings.als_iterations,
    }
