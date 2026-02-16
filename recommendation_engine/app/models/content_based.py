"""
Content-based filtering — TF-IDF on book metadata + cosine similarity.

Uses genre, author, and description to build feature vectors.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import structlog
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.model_store import model_store

logger = structlog.get_logger()


class ContentBasedRecommender:
    """Content-based recommender using TF-IDF on book metadata."""

    def __init__(self):
        self.tfidf_matrix = None
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.book_ids: list[int] = []
        self.book_metadata: dict[int, dict] = {}
        self._loaded = False

    def load(self) -> bool:
        """Load pre-trained artifacts from model store."""
        self.tfidf_matrix = model_store.load_artifact("content_tfidf_matrix")
        self.vectorizer = model_store.load_artifact("content_vectorizer")
        book_data = model_store.load_artifact("content_book_data")

        if self.tfidf_matrix is not None and book_data is not None:
            self.book_ids = book_data.get("book_ids", [])
            self.book_metadata = book_data.get("metadata", {})
            self._loaded = True
            logger.info("content_model_loaded", n_books=len(self.book_ids))
            return True

        logger.warning("content_model_not_available")
        return False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def get_similar_books(self, book_id: int, n: int = 10) -> list[dict]:
        """Find N most similar books based on content features."""
        if not self._loaded:
            return []

        if book_id not in self.book_ids:
            logger.warning("book_not_in_content_model", book_id=book_id)
            return []

        idx = self.book_ids.index(book_id)
        similarity_scores = cosine_similarity(
            self.tfidf_matrix[idx : idx + 1], self.tfidf_matrix
        ).flatten()

        # Get top N+1 (excluding self)
        top_indices = np.argsort(similarity_scores)[::-1][1 : n + 1]

        results = []
        for i in top_indices:
            bid = self.book_ids[i]
            meta = self.book_metadata.get(bid, {})
            results.append(
                {
                    "book_id": bid,
                    "title": meta.get("title", "Unknown"),
                    "author": meta.get("author", "Unknown"),
                    "genre": meta.get("genre", "Unknown"),
                    "score": float(similarity_scores[i]),
                    "reason": "content-based",
                }
            )

        return results

    def get_recommendations_for_user(
        self, liked_book_ids: list[int], n: int = 10
    ) -> list[dict]:
        """
        Get content-based recommendations for a user based on their liked books.
        Aggregates similarity scores across all liked books.
        """
        if not self._loaded or not liked_book_ids:
            return []

        aggregate_scores = np.zeros(len(self.book_ids))

        for book_id in liked_book_ids:
            if book_id not in self.book_ids:
                continue
            idx = self.book_ids.index(book_id)
            scores = cosine_similarity(
                self.tfidf_matrix[idx : idx + 1], self.tfidf_matrix
            ).flatten()
            aggregate_scores += scores

        # Exclude already liked books
        for book_id in liked_book_ids:
            if book_id in self.book_ids:
                idx = self.book_ids.index(book_id)
                aggregate_scores[idx] = -1.0

        top_indices = np.argsort(aggregate_scores)[::-1][:n]

        results = []
        for i in top_indices:
            if aggregate_scores[i] <= 0:
                continue
            bid = self.book_ids[i]
            meta = self.book_metadata.get(bid, {})
            results.append(
                {
                    "book_id": bid,
                    "title": meta.get("title", "Unknown"),
                    "author": meta.get("author", "Unknown"),
                    "genre": meta.get("genre", "Unknown"),
                    "score": float(aggregate_scores[i]),
                    "reason": "content-based",
                }
            )

        return results


# Singleton
content_recommender = ContentBasedRecommender()
