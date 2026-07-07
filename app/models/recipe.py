from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from app import db
from app.models.common import PaginationMixin


class Recipe(PaginationMixin, db.Model):
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
    prep_time = db.Column(db.Integer)
    cook_time = db.Column(db.Integer)
    servings = db.Column(db.Integer)
    category = db.Column(db.String(50))
    status = db.Column(db.String(20), nullable=False, default="public", server_default="public")
    status_before_deactivation = db.Column(db.String(20))
    moderation_status = db.Column(db.String(20), nullable=False, default="allowed", server_default="allowed")
    moderation_issues = db.Column(db.JSON, nullable=False, default=list, server_default="[]")
    status_before_moderation = db.Column(db.String(20))
    moderated_at = db.Column(db.DateTime)
    moderation_notification_signature = db.Column(db.String(128))
    image_id = db.Column(db.String(64), index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    scores = db.relationship("RecipeScore", back_populates="recipe", cascade="all, delete-orphan")

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


class RecipeScore(db.Model):
    __tablename__ = "recipe_scores"
    __table_args__ = (
        db.UniqueConstraint("recipe_id", "user_id", name="uq_recipe_scores_recipe_user"),
        db.CheckConstraint("score >= 1 AND score <= 5", name="ck_recipe_scores_score"),
    )

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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
