"""
Collaborative filtering — ALS matrix factorization via `implicit` library.

Learns latent factors from user-book interaction matrix.
"""

from __future__ import annotations

from typing import Optional

import structlog
from scipy.sparse import csr_matrix

from app.model_store import model_store

logger = structlog.get_logger()


class CollaborativeRecommender:
    """Collaborative filtering using ALS (Alternating Least Squares)."""

    def __init__(self):
        self.model = None
        self.user_item_matrix: Optional[csr_matrix] = None
        self.user_id_map: dict[int, int] = {}  # user_id → matrix index
        self.item_id_map: dict[int, int] = {}  # book_id → matrix index
        self.reverse_item_map: dict[int, int] = {}  # matrix index → book_id
        self.book_metadata: dict[int, dict] = {}
        self._loaded = False

    def load(self) -> bool:
        """Load pre-trained ALS model and mappings."""
        self.model = model_store.load_artifact("collab_als_model")
        mappings = model_store.load_artifact("collab_mappings")
        self.user_item_matrix = model_store.load_artifact("collab_user_item_matrix")

        if self.model is not None and mappings is not None:
            self.user_id_map = mappings.get("user_id_map", {})
            self.item_id_map = mappings.get("item_id_map", {})
            self.reverse_item_map = {v: k for k, v in self.item_id_map.items()}
            self.book_metadata = mappings.get("book_metadata", {})
            self._loaded = True
            logger.info(
                "collab_model_loaded",
                n_users=len(self.user_id_map),
                n_items=len(self.item_id_map),
            )
            return True

        logger.warning("collab_model_not_available")
        return False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def get_user_recommendations(self, user_id: int, n: int = 10) -> list[dict]:
        """Get top-N recommendations for a user via collaborative filtering."""
        if not self._loaded or self.model is None:
            return []

        if user_id not in self.user_id_map:
            logger.info("user_not_in_collab_model", user_id=user_id)
            return []

        user_idx = self.user_id_map[user_id]

        try:
            # implicit library recommend method
            item_indices, scores = self.model.recommend(
                user_idx,
                self.user_item_matrix[user_idx],
                N=n,
                filter_already_liked_items=True,
            )

            results = []
            for item_idx, score in zip(item_indices, scores):
                book_id = self.reverse_item_map.get(int(item_idx))
                if book_id is None:
                    continue
                meta = self.book_metadata.get(book_id, {})
                results.append(
                    {
                        "book_id": book_id,
                        "title": meta.get("title", "Unknown"),
                        "author": meta.get("author", "Unknown"),
                        "genre": meta.get("genre", "Unknown"),
                        "score": float(score),
                        "reason": "collaborative",
                    }
                )
            return results

        except Exception as e:
            logger.error("collab_recommend_error", error=str(e), user_id=user_id)
            return []

    def get_similar_items(self, book_id: int, n: int = 10) -> list[dict]:
        """Find N most similar books based on collaborative filtering."""
        if not self._loaded or self.model is None:
            return []

        if book_id not in self.item_id_map:
            return []

        item_idx = self.item_id_map[book_id]

        try:
            item_indices, scores = self.model.similar_items(item_idx, N=n + 1)

            results = []
            for idx, score in zip(item_indices, scores):
                bid = self.reverse_item_map.get(int(idx))
                if bid is None or bid == book_id:
                    continue
                meta = self.book_metadata.get(bid, {})
                results.append(
                    {
                        "book_id": bid,
                        "title": meta.get("title", "Unknown"),
                        "author": meta.get("author", "Unknown"),
                        "genre": meta.get("genre", "Unknown"),
                        "score": float(score),
                        "reason": "collaborative",
                    }
                )
            return results[:n]

        except Exception as e:
            logger.error("collab_similar_error", error=str(e), book_id=book_id)
            return []


# Singleton
collab_recommender = CollaborativeRecommender()
