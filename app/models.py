from datetime import datetime, timezone
from typing import Any, cast

from flask_login import UserMixin
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash

from app import db

# Association table for user <-> recipe favorites (many-to-many)
users_favorites = db.Table(
    "users_favorites",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("recipe_id", db.Integer, db.ForeignKey("recipes.id"), primary_key=True),
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
    ROLE_FIJNPROEVER = 1
    ROLE_LEERLING_KOK = 2
    ROLE_ZELFSTANDIG_KOK = 3
    ROLE_CHEF_DE_PARTIE = 4
    ROLE_SOUS_CHEF = 5
    ROLE_CHEF_DE_CUISINE = 6
    VALID_ROLES = (
        ROLE_FIJNPROEVER,
        ROLE_LEERLING_KOK,
        ROLE_ZELFSTANDIG_KOK,
        ROLE_CHEF_DE_PARTIE,
        ROLE_SOUS_CHEF,
        ROLE_CHEF_DE_CUISINE,
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(
        db.Integer,
        nullable=False,
        default=ROLE_FIJNPROEVER,
        server_default=text(str(ROLE_FIJNPROEVER)),
    )
    is_active = db.Column(  # pyright: ignore[reportIncompatibleMethodOverride]
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )
    creator_request_pending = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.false()
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship with recipes
    recipes = db.relationship(
        "Recipe", backref="author", lazy="dynamic", cascade="all, delete-orphan"
    )

    # Favorite recipes (many-to-many to Recipe)
    favorites = db.relationship(
        "Recipe",
        secondary=users_favorites,
        lazy="dynamic",
        backref=db.backref("favorited_by", lazy="dynamic"),
    )
    scores = db.relationship(
        "RecipeScore", back_populates="user", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def set_password(self, password):
        """Hash and set the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if the provided password matches the hash."""
        return check_password_hash(self.password_hash, password)

    def get_role_label(self):
        role_labels = {
            self.ROLE_FIJNPROEVER: "Fijnproever",
            self.ROLE_LEERLING_KOK: "Leerling Kok",
            self.ROLE_ZELFSTANDIG_KOK: "Zelfstandig Kok",
            self.ROLE_CHEF_DE_PARTIE: "Chef de Partie",
            self.ROLE_SOUS_CHEF: "Sous Chef",
            self.ROLE_CHEF_DE_CUISINE: "Chef de Cuisine",
        }
        return role_labels.get(self.role, "Onbekend")

    @property
    def is_admin(self):
        return self.role == self.ROLE_CHEF_DE_CUISINE

    @property
    def is_creator(self):
        return self.role >= self.ROLE_LEERLING_KOK

    @property
    def can_create_recipes(self):
        return bool(self.is_active and self.is_creator)

    @property
    def can_score_recipes(self):
        return bool(self.is_active and self.role >= self.ROLE_FIJNPROEVER)

    def __repr__(self):
        return f"<User {self.username}>"


class Recipe(PaginationMixin, db.Model):
    """Recipe model for storing cooking recipes."""

    __tablename__ = "recipes"
    STATUS_PUBLIC = "public"
    STATUS_DRAFT = "draft"
    STATUS_DEACTIVATED = "deactivated"
    VALID_STATUSES = (STATUS_PUBLIC, STATUS_DRAFT, STATUS_DEACTIVATED)

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    ingredients = db.Column(db.JSON, nullable=False, default=list)
    instructions = db.Column(db.JSON, nullable=False, default=list)
    prep_time = db.Column(db.Integer)  # in minutes
    cook_time = db.Column(db.Integer)  # in minutes
    servings = db.Column(db.Integer)
    category = db.Column(db.String(50))
    status = db.Column(
        db.String(20), nullable=False, default="public", server_default="public"
    )
    status_before_deactivation = db.Column(db.String(20))

    # File-backed recipe image identifier (stored as DATAROOT/recipe/<image_id>.webp)
    image_id = db.Column(db.String(64), index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Foreign key to User
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    scores = db.relationship(
        "RecipeScore", back_populates="recipe", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    @property
    def score_count(self):
        scores = cast(list["RecipeScore"], self.scores)
        return len(scores)

    @property
    def score_average(self):
        scores = cast(list["RecipeScore"], self.scores)
        if not scores:
            return None
        total = sum(score.score for score in scores)
        return round(total / len(scores), 1)

    def score_for_user(self, user_id):
        scores = cast(list["RecipeScore"], self.scores)
        for score in scores:
            if score.user_id == user_id:
                return score
        return None

    def is_visible_to(self, user):
        if self.status == self.STATUS_PUBLIC:
            return True
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if not getattr(user, "is_active", False):
            return False
        if getattr(user, "is_admin", False):
            return True
        return user.id == self.user_id

    @property
    def has_image(self):
        return bool(self.image_id)

    def __repr__(self):
        return f"<Recipe {self.title}>"


class RecipeScore(db.Model):
    """Per-user recipe score."""

    __tablename__ = "recipe_scores"
    __table_args__ = (
        db.UniqueConstraint(
            "recipe_id", "user_id", name="uq_recipe_scores_recipe_user"
        ),
        db.CheckConstraint("score >= 1 AND score <= 5", name="ck_recipe_scores_score"),
    )

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(
        db.Integer, db.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    recipe = db.relationship("Recipe", back_populates="scores")
    user = db.relationship("User", back_populates="scores")

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<RecipeScore recipe={self.recipe_id} user={self.user_id} score={self.score}>"


class OTC(db.Model):
    """One-Time Code model for user registration."""

    __tablename__ = "otc"
    __table_args__ = (db.Index("ix_otc_expires_at", "expires_at"),)
    code = db.Column(db.String(8), primary_key=True, unique=True, nullable=False)
    purpose = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def is_expired(self):
        return datetime.now(timezone.utc) >= self.expires_at

    def __repr__(self):
        return f"<OTC code={self.code} expires_at={self.expires_at}>"
