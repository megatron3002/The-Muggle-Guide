"""Book CRUD routes — public read, admin-only write."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.book import Book
from app.schemas.book import BookCreate, BookListResponse, BookResponse, BookUpdate

router = APIRouter(prefix="/books", tags=["Books"])


@router.get("", response_model=BookListResponse)
async def list_books(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    genre: str | None = None,
    author: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Paginated book listing with optional genre/author/search filters."""
    query = select(Book)

    if genre:
        query = query.where(Book.genre.ilike(f"%{genre}%"))
    if author:
        query = query.where(Book.author.ilike(f"%{author}%"))
    if search:
        query = query.where(Book.title.ilike(f"%{search}%") | Book.author.ilike(f"%{search}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.order_by(Book.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    books = result.scalars().all()

    return BookListResponse(
        books=[BookResponse.model_validate(b) for b in books],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Get a single book by ID."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return BookResponse.model_validate(book)


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    data: BookCreate,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """Create a new book (admin only)."""
    book = Book(**data.model_dump())
    db.add(book)
    await db.flush()
    return BookResponse.model_validate(book)


@router.put("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: int,
    data: BookUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """Update a book (admin only)."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(book, field, value)

    await db.flush()
    return BookResponse.model_validate(book)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """Delete a book (admin only)."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    await db.delete(book)
