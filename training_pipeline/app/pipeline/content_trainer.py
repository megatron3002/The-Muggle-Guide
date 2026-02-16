"""
Content-based model trainer — fits TF-IDF vectorizer on book metadata.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
import structlog
from sklearn.feature_extraction.text import TfidfVectorizer

from app.config import get_settings
from app.pipeline.model_store import save_artifact

logger = structlog.get_logger()
settings = get_settings()


def train_content_model(books_df: pd.DataFrame) -> dict:
    """
    Train content-based model:
    1. Combine genre + author + description into a single text feature
    2. Fit TF-IDF vectorizer
    3. Save vectorizer and TF-IDF matrix
    """
    logger.info("training_content_model", n_books=len(books_df))

    # Feature engineering: combine text features
    books_df = books_df.copy()
    books_df["description"] = books_df["description"].fillna("")
    books_df["combined_features"] = (
        books_df["genre"] + " " +
        books_df["author"] + " " +
        books_df["description"]
    )

    # Fit TF-IDF
    vectorizer = TfidfVectorizer(
        max_features=settings.tfidf_max_features,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
    )
    tfidf_matrix = vectorizer.fit_transform(books_df["combined_features"])

    # Prepare book data for the recommender
    book_ids = books_df["id"].tolist()
    book_metadata = {}
    for _, row in books_df.iterrows():
        book_metadata[row["id"]] = {
            "title": row["title"],
            "author": row["author"],
            "genre": row["genre"],
        }

    # Save artifacts
    save_artifact("content_tfidf_matrix", tfidf_matrix)
    save_artifact("content_vectorizer", vectorizer)
    save_artifact("content_book_data", {
        "book_ids": book_ids,
        "metadata": book_metadata,
    })

    logger.info("content_model_trained", n_features=tfidf_matrix.shape[1])

    return {
        "n_books": len(book_ids),
        "n_features": tfidf_matrix.shape[1],
        "vocabulary_size": len(vectorizer.vocabulary_),
    }
