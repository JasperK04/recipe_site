from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from app import db
from app.models.common import PaginationMixin

if TYPE_CHECKING:
    from app.models.user import User


class Recipe(PaginationMixin, db.Model):
    __tablename__ = "recipes"

    STATUS_PUBLIC = "public"
    STATUS_PRIVATE = "private"
    # Kept as a source-compatible alias for integrations that imported the
    # constant.  Persisted recipes use the ``private`` value exclusively.
    STATUS_DRAFT = STATUS_PRIVATE
    STATUS_DEACTIVATED = "deactivated"
    VALID_STATUSES = (STATUS_PUBLIC, STATUS_PRIVATE, STATUS_DEACTIVATED)

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    ingredients = db.Column(db.JSON, nullable=False, default=list)
    instructions = db.Column(db.JSON, nullable=False, default=list)
    prep_time = db.Column(db.Integer)
    cook_time = db.Column(db.Integer)
    servings = db.Column(db.Integer)
    category = db.Column(db.String(50))
    status = db.Column(
        db.String(20), nullable=False, default="public", server_default="public"
    )
    status_before_deactivation = db.Column(db.String(20))
    moderation_status = db.Column(
        db.String(20), nullable=False, default="allowed", server_default="allowed"
    )
    moderation_issues = db.Column(
        db.JSON, nullable=False, default=list, server_default="[]"
    )
    status_before_moderation = db.Column(db.String(20))
    moderated_at = db.Column(db.DateTime)
    moderation_notification_signature = db.Column(db.String(128))
    image_id = db.Column(db.String(64), index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    if TYPE_CHECKING:
        author: User
    original_recipe_id = db.Column(
        db.Integer,
        db.ForeignKey("recipes.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "original_recipe_id", name="uq_recipes_user_original_recipe"
        ),
    )

    scores = db.relationship(
        "RecipeScore", back_populates="recipe", cascade="all, delete-orphan"
    )
    original_recipe = db.relationship(
        "Recipe",
        remote_side=[id],
        backref=db.backref("adaptations"),
    )
    dependencies = db.relationship(
        "Recipe",
        secondary="recipe_dependencies",
        primaryjoin="Recipe.id == RecipeDependency.dependent_recipe_id",
        secondaryjoin="Recipe.id == RecipeDependency.dependency_recipe_id",
        back_populates="dependents",
        lazy="selectin",
    )
    dependents = db.relationship(
        "Recipe",
        secondary="recipe_dependencies",
        primaryjoin="Recipe.id == RecipeDependency.dependency_recipe_id",
        secondaryjoin="Recipe.id == RecipeDependency.dependent_recipe_id",
        back_populates="dependencies",
        lazy="selectin",
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

    @property
    def url_title(self) -> str:
        """A readable URL suffix; recipe lookup always uses ``id`` only."""
        normalized = unicodedata.normalize("NFKD", self.title)
        ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-") or "recept"

    @property
    def is_flagged_by_moderation(self) -> bool:
        return self.moderation_status == "flagged"

    @property
    def moderation_issue_messages(self) -> list[str]:
        issues = self.moderation_issues or []
        messages: list[str] = []
        for issue in issues:
            if isinstance(issue, dict):
                message = issue.get("message")
                if message:
                    messages.append(str(message))
            elif issue:
                messages.append(str(issue))
        return messages

    def __repr__(self):
        return f"<Recipe {self.title}>"


class RecipeDependency(db.Model):
    __tablename__ = "recipe_dependencies"
    __table_args__ = (
        db.UniqueConstraint(
            "dependent_recipe_id",
            "dependency_recipe_id",
            name="uq_recipe_dependencies_edge",
        ),
    )

    dependent_recipe_id = db.Column(
        db.Integer,
        db.ForeignKey("recipes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    dependency_recipe_id = db.Column(
        db.Integer,
        db.ForeignKey("recipes.id", ondelete="CASCADE"),
        primary_key=True,
    )

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)


class RecipeScore(db.Model):
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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    recipe = db.relationship("Recipe", back_populates="scores")
    user = db.relationship("User", back_populates="scores")

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<RecipeScore recipe={self.recipe_id} user={self.user_id} score={self.score}>"
