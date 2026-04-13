from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db

# Association table for recipe <-> machine many-to-many relationship
recipe_machines = db.Table(
    "recipe_machines",
    db.Column("recipe_id", db.Integer, db.ForeignKey("recipes.id"), primary_key=True),
    db.Column(
        "machine_id",
        db.Integer,
        db.ForeignKey("kitchen_machines.id"),
        primary_key=True,
    ),
)


class PaginationMixin:
    """Mixin providing a standard paginate helper for models.

    Usage:
      - Call `Model.paginate(page, per_page, query=optional_query, order_by=optional_order)`
      - Returns a dict with `items`, `total`, `page`, `per_page`, `pages`,
        `has_next`, `has_prev`, `next_page`, `prev_page` and `pagination_obj`.
    """

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

        # Leverage Flask-SQLAlchemy's `paginate` if available
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


class User(UserMixin, db.Model):
    """User model for authentication."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship with recipes
    recipes = db.relationship(
        "Recipe", backref="author", lazy="dynamic", cascade="all, delete-orphan"
    )

    # Relationship with kitchen machines (many-to-many)
    # Previously users could be linked to machines; this association was removed.

    def set_password(self, password):
        """Hash and set the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if the provided password matches the hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Recipe(PaginationMixin, db.Model):
    """Recipe model for storing cooking recipes."""

    __tablename__ = "recipes"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    ingredients = db.Column(db.JSON, nullable=False, default=list)
    instructions = db.Column(db.JSON, nullable=False, default=list)
    prep_time = db.Column(db.Integer)  # in minutes
    cook_time = db.Column(db.Integer)  # in minutes
    servings = db.Column(db.Integer)
    category = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Foreign key to User
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Relationship with kitchen machines (many-to-many)
    required_machines = db.relationship(
        "KitchenMachine",
        secondary=recipe_machines,
        lazy="subquery",
        backref=db.backref("recipes", lazy=True),
    )

    def __repr__(self):
        return f"<Recipe {self.title}>"


class KitchenMachine(db.Model):
    """Kitchen machine/equipment model."""

    __tablename__ = "kitchen_machines"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200))

    def __repr__(self):
        return f"<KitchenMachine {self.name}>"
