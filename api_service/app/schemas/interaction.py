"""Interaction schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InteractionCreate(BaseModel):
    book_id: int
    interaction_type: str = Field(..., pattern=r"^(view|like|rate|purchase|bookmark)$")
    rating: Optional[float] = Field(None, ge=1.0, le=5.0)


class InteractionResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    interaction_type: str
    rating: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}
