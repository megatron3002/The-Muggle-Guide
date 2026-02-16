"""Book schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    author: str = Field(..., min_length=1, max_length=255)
    genre: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    isbn: Optional[str] = Field(None, max_length=20)
    published_year: Optional[int] = Field(None, ge=1000, le=2100)


class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    author: Optional[str] = Field(None, min_length=1, max_length=255)
    genre: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    isbn: Optional[str] = Field(None, max_length=20)
    published_year: Optional[int] = Field(None, ge=1000, le=2100)


class BookResponse(BaseModel):
    id: int
    title: str
    author: str
    genre: str
    description: Optional[str]
    isbn: Optional[str]
    published_year: Optional[int]
    avg_rating: float
    total_interactions: int
    created_at: datetime

    model_config = {"from_attributes": True}


class BookListResponse(BaseModel):
    books: list[BookResponse]
    total: int
    page: int
    page_size: int
