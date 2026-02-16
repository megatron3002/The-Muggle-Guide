"""
Hybrid recommender — weighted combination of collaborative and content-based.

Falls back to content-only or popularity-based when collaborative is unavailable.
"""

from __future__ import annotations

import structlog

from app.config import get_settings
from app.models.collaborative import collab_recommender
from app.models.content_based import content_recommender

logger = structlog.get_logger()
settings = get_settings()


class HybridRecommender:
    """Blends collaborative and content-based recommendations."""

    def __init__(self, alpha: float | None = None):
        self.alpha = alpha or settings.hybrid_alpha  # Weight for collaborative

    def get_recommendations(
        self,
        user_id: int,
        liked_book_ids: list[int],
        n: int = 10,
    ) -> tuple[list[dict], str]:
        """
        Get hybrid recommendations.
        Returns (recommendations, strategy_used).
        """
        collab_results = []
        content_results = []

        # Try collaborative
        if collab_recommender.is_loaded:
            collab_results = collab_recommender.get_user_recommendations(user_id, n=n * 2)

        # Try content-based
        if content_recommender.is_loaded and liked_book_ids:
            content_results = content_recommender.get_recommendations_for_user(liked_book_ids, n=n * 2)

        # Determine strategy
        if collab_results and content_results:
            merged = self._merge_results(collab_results, content_results, n)
            return merged, "hybrid"
        elif collab_results:
            return collab_results[:n], "collaborative"
        elif content_results:
            return content_results[:n], "content-based"
        else:
            return [], "none"

    def get_similar_books(self, book_id: int, n: int = 10) -> tuple[list[dict], str]:
        """Get similar books using best available strategy."""
        collab_similar = []
        content_similar = []

        if collab_recommender.is_loaded:
            collab_similar = collab_recommender.get_similar_items(book_id, n=n * 2)

        if content_recommender.is_loaded:
            content_similar = content_recommender.get_similar_books(book_id, n=n * 2)

        if collab_similar and content_similar:
            merged = self._merge_results(collab_similar, content_similar, n)
            return merged, "hybrid"
        elif collab_similar:
            return collab_similar[:n], "collaborative"
        elif content_similar:
            return content_similar[:n], "content-based"
        else:
            return [], "none"

    def _merge_results(
        self,
        collab: list[dict],
        content: list[dict],
        n: int,
    ) -> list[dict]:
        """
        Merge collaborative and content-based results using weighted scoring.
        Deduplicates by book_id, keeping the higher blended score.
        """
        # Normalize scores within each set
        collab_scores = self._normalize([r["score"] for r in collab]) if collab else []
        content_scores = self._normalize([r["score"] for r in content]) if content else []

        merged: dict[int, dict] = {}

        for i, rec in enumerate(collab):
            bid = rec["book_id"]
            score = collab_scores[i] * self.alpha
            if bid not in merged or score > merged[bid]["score"]:
                merged[bid] = {**rec, "score": score, "reason": "collaborative"}

        for i, rec in enumerate(content):
            bid = rec["book_id"]
            score = content_scores[i] * (1 - self.alpha)
            if bid in merged:
                # Blend: add content score to existing collaborative score
                merged[bid]["score"] += score
                merged[bid]["reason"] = "hybrid"
            elif bid not in merged:
                merged[bid] = {**rec, "score": score, "reason": "content-based"}

        # Sort by blended score
        sorted_results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results[:n]

    @staticmethod
    def _normalize(scores: list[float]) -> list[float]:
        if not scores:
            return []
        min_s, max_s = min(scores), max(scores)
        if max_s == min_s:
            return [1.0] * len(scores)
        return [(s - min_s) / (max_s - min_s) for s in scores]


# Singleton
hybrid_recommender = HybridRecommender()
