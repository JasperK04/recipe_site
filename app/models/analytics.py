from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from app import db


class AnalyticsEvent(db.Model):
    __tablename__ = "analytics_events"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(40), nullable=False, index=True)
    occurred_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    path = db.Column(db.String(500), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    status_code = db.Column(db.Integer)
    recipe_id = db.Column(
        db.Integer,
        db.ForeignKey("recipes.id", ondelete="SET NULL"),
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    visitor_id = db.Column(db.String(64), index=True)
    duration_ms = db.Column(db.Integer)
    error_type = db.Column(db.String(120))
    referrer = db.Column(db.String(500))
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)


class AnalyticsErrorGroup(db.Model):
    __tablename__ = "analytics_error_groups"

    id = db.Column(db.Integer, primary_key=True)
    bucket_started_at = db.Column(db.DateTime, nullable=True, index=True)
    first_occurred_at = db.Column(db.DateTime, nullable=False, index=True)
    last_occurred_at = db.Column(db.DateTime, nullable=False, index=True)
    occurrence_count = db.Column(db.Integer, nullable=False, default=1)
    status_code = db.Column(db.Integer)
    path = db.Column(db.String(500), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    error_type = db.Column(db.String(120))
    referrer = db.Column(db.String(500))

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    @property
    def referrer_path(self) -> str | None:
        """Return only the route and query string from the recorded referrer."""
        if not self.referrer:
            return None
        parsed = urlsplit(self.referrer)
        path = parsed.path or "/"
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{path}?{parsed.query}" if parsed.query else path


class AnalyticsDaily(db.Model):
    __tablename__ = "analytics_daily"
    __table_args__ = (
        db.UniqueConstraint(
            "day", "event_type", "recipe_id", name="uq_analytics_daily_event"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Date, nullable=False, index=True)
    event_type = db.Column(db.String(40), nullable=False)
    recipe_id = db.Column(db.Integer, index=True)
    event_count = db.Column(db.Integer, nullable=False, default=0)

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)


class AnalyticsDailyVisitor(db.Model):
    __tablename__ = "analytics_daily_visitors"
    __table_args__ = (
        db.UniqueConstraint("day", "visitor_id", name="uq_analytics_daily_visitor"),
    )

    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Date, nullable=False, index=True)
    visitor_id = db.Column(db.String(64), nullable=False, index=True)

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
