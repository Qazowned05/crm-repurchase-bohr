from math import ceil
from typing import TypeVar

from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


def page_params(
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=200),
) -> tuple[int | None, int | None]:
    """Keep legacy array responses until a caller explicitly requests pagination."""
    return page, page_size


def paginated_scalars(db: Session, query, page: int | None, page_size: int | None) -> list[T] | dict:
    if page is None and page_size is None:
        return list(db.scalars(query))
    current_page = page or 1
    size = page_size or 50
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = list(db.scalars(query.limit(size).offset((current_page - 1) * size)))
    return {"items": items, "page": current_page, "page_size": size, "total": total, "pages": ceil(total / size) if total else 0}


def paginate_items(items: list[T], page: int | None, page_size: int | None) -> list[T] | dict:
    if page is None and page_size is None:
        return items
    current_page = page or 1
    size = page_size or 50
    total = len(items)
    return {"items": items[(current_page - 1) * size: current_page * size], "page": current_page, "page_size": size, "total": total, "pages": ceil(total / size) if total else 0}
