from __future__ import annotations

from app import db


users_favorites = db.Table(
    "users_favorites",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("recipe_id", db.Integer, db.ForeignKey("recipes.id"), primary_key=True),
)


class PaginationMixin:
    """Mixin providing a standard paginate helper for models."""

    @classmethod
    def paginate(cls, page=1, per_page=10, query=None, order_by=None):
        try:
            page = int(page) if page and int(page) > 0 else 1
        except Exception:
            page = 1
        try:
            per_page = int(per_page) if per_page and int(per_page) > 0 else 10
        except Exception:
            per_page = 10

        q = query or getattr(cls, "query")
        if order_by is not None:
            q = q.order_by(order_by)

        pagination = q.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "items": pagination.items,
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
            "next_page": pagination.next_num if pagination.has_next else None,
            "prev_page": pagination.prev_num if pagination.has_prev else None,
            "pagination_obj": pagination,
        }
