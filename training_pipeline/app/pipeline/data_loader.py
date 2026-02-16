"""
Data loader — fetches books and interactions from PostgreSQL into DataFrames.
Includes basic data validation checks.
"""

from __future__ import annotations

import structlog
import pandas as pd
from sqlalchemy import create_engine, text

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


def load_books() -> pd.DataFrame:
    """Load all books from the database."""
    engine = create_engine(settings.database_dsn)
    query = "SELECT id, title, author, genre, description, avg_rating, total_interactions FROM books"
    df = pd.read_sql(query, engine)
    engine.dispose()

    logger.info("books_loaded", count=len(df))

    # Data validation
    assert len(df) > 0, "No books found in database"
    assert not df["id"].duplicated().any(), "Duplicate book IDs found"

    return df


def load_interactions() -> pd.DataFrame:
    """Load all user-book interactions from the database."""
    engine = create_engine(settings.database_dsn)
    query = """
        SELECT id, user_id, book_id, interaction_type, rating, created_at
        FROM user_book_interactions
        ORDER BY created_at
    """
    df = pd.read_sql(query, engine)
    engine.dispose()

    logger.info("interactions_loaded", count=len(df))

    # Data validation
    if len(df) > 0:
        assert not df[["user_id", "book_id"]].isnull().any().any(), "Null user/book IDs"
        n_users = df["user_id"].nunique()
        n_items = df["book_id"].nunique()
        logger.info("interaction_stats", n_users=n_users, n_items=n_items, sparsity=round(1 - len(df) / (n_users * n_items), 4))

    return df


def load_users() -> pd.DataFrame:
    """Load user IDs for mapping."""
    engine = create_engine(settings.database_dsn)
    query = "SELECT id FROM users WHERE is_active = true"
    df = pd.read_sql(query, engine)
    engine.dispose()
    return df
