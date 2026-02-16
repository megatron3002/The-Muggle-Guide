"""
Cold-start handling for new users and new books.

- New users (no interactions): popularity-based recommendations
- New books (no interactions): content-based neighbors only
"""

from __future__ import annotations

import structlog

from app.model_store import model_store
from app.models.content_based import content_recommender

logger = structlog.get_logger()


class ColdStartHandler:
    """Handles cold-start scenarios for new users and items."""

    def __init__(self):
        self.popular_books: list[dict] = []
        self._loaded = False

    def load(self) -> bool:
        """Load popularity-based fallback data."""
        data = model_store.load_artifact("popularity_data")
        if data is not None:
            self.popular_books = data.get("popular_books", [])
            self._loaded = True
            logger.info("cold_start_data_loaded", n_popular=len(self.popular_books))
            return True
        logger.warning("cold_start_data_not_available")
        return False

    def get_popular_recommendations(self, n: int = 10) -> list[dict]:
        """Return the most popular books (for new users with no interactions)."""
        if not self._loaded:
            return []

        results = []
        for book in self.popular_books[:n]:
            results.append(
                {
                    "book_id": book["book_id"],
                    "title": book.get("title", "Unknown"),
                    "author": book.get("author", "Unknown"),
                    "genre": book.get("genre", "Unknown"),
                    "score": book.get("score", 0.0),
                    "reason": "popularity",
                }
            )
        return results

    def get_new_book_neighbors(self, book_id: int, n: int = 10) -> list[dict]:
        """For a new book with no interactions, use content-based similarity."""
        if content_recommender.is_loaded:
            return content_recommender.get_similar_books(book_id, n)
        return []


# Singleton
cold_start_handler = ColdStartHandler()
