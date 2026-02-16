"""User-Book interaction tracking routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.book import Book
from app.models.interaction import InteractionType, UserBookInteraction
from app.schemas.interaction import InteractionCreate, InteractionResponse
from app.services.cache import invalidate

router = APIRouter(prefix="/interactions", tags=["Interactions"])


@router.post("", response_model=InteractionResponse, status_code=status.HTTP_201_CREATED)
async def create_interaction(
    data: InteractionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Log a user-book interaction (idempotent for view/like/bookmark)."""
    user_id = current_user["user_id"]

    # Verify book exists
    result = await db.execute(select(Book).where(Book.id == data.book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Idempotency: for view/like/bookmark, check if same interaction exists recently
    interaction_type = InteractionType(data.interaction_type)
    if interaction_type in (InteractionType.VIEW, InteractionType.LIKE, InteractionType.BOOKMARK):
        existing = await db.execute(
            select(UserBookInteraction).where(
                UserBookInteraction.user_id == user_id,
                UserBookInteraction.book_id == data.book_id,
                UserBookInteraction.interaction_type == interaction_type,
            )
        )
        if existing.scalar_one_or_none():
            # Return existing interaction (idempotent)
            return InteractionResponse.model_validate(existing.scalar_one_or_none())

    interaction = UserBookInteraction(
        user_id=user_id,
        book_id=data.book_id,
        interaction_type=interaction_type,
        rating=data.rating if interaction_type == InteractionType.RATE else None,
    )
    db.add(interaction)

    # Update book stats
    book.total_interactions += 1
    if data.rating is not None and interaction_type == InteractionType.RATE:
        # Recalculate average rating
        result = await db.execute(
            select(func.avg(UserBookInteraction.rating)).where(
                UserBookInteraction.book_id == data.book_id,
                UserBookInteraction.rating.isnot(None),
            )
        )
        avg = result.scalar()
        if avg:
            book.avg_rating = round(float(avg), 2)

    await db.flush()

    # Invalidate recommendation cache for this user
    await invalidate(f"rec:user:{user_id}:*")

    return InteractionResponse.model_validate(interaction)


@router.get("/me", response_model=list[InteractionResponse])
async def list_my_interactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List current user's interactions."""
    user_id = current_user["user_id"]
    offset = (page - 1) * page_size
    result = await db.execute(
        select(UserBookInteraction)
        .where(UserBookInteraction.user_id == user_id)
        .order_by(UserBookInteraction.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    interactions = result.scalars().all()
    return [InteractionResponse.model_validate(i) for i in interactions]
