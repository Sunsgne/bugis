"""Shared pagination helpers."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")
ItemT = TypeVar("ItemT")


class PaginatedResponse(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    total: int
    page: int
    page_size: int


def paginate_query(
    db: Session,
    stmt: Select[tuple[T]],
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[T], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(db.scalar(count_stmt) or 0)
    offset = (page - 1) * page_size
    items = list(db.execute(stmt.offset(offset).limit(page_size)).scalars().all())
    return items, total


def paginated(
    items: list[ItemT],
    *,
    total: int,
    page: int,
    page_size: int,
) -> PaginatedResponse[ItemT]:
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
