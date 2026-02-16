"""Recommendation response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class RecommendedBook(BaseModel):
    book_id: int
    title: str
    author: str
    genre: str
    score: float
    reason: str  # e.g. "collaborative", "content-based", "popularity"


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: list[RecommendedBook]
    strategy: str  # "hybrid", "content", "collaborative", "cold_start"


class SimilarBooksResponse(BaseModel):
    book_id: int
    similar_books: list[RecommendedBook]


class ModelStatusResponse(BaseModel):
    status: str
    last_trained: str | None
    model_version: str | None
    metrics: dict | None


class RetrainResponse(BaseModel):
    task_id: str
    status: str
    message: str
