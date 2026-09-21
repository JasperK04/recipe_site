from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Any

from flask import current_app, g, request
from flask_login import current_user
from sqlalchemy import delete, func

from app import db
from app.models import (
    AnalyticsDaily,
    AnalyticsDailyVisitor,
    AnalyticsErrorGroup,
    AnalyticsEvent,
    Recipe,
)

PAGE_VIEW_EVENTS = ("page_view", "recipe_view")
ROLLUP_EVENTS = PAGE_VIEW_EVENTS + ("error",)
VISITOR_COOKIE = "analytics_visitor"


class Analytics:
    """Best-effort application analytics with raw events and daily rollups."""

    @staticmethod
    def visitor_id() -> str:
        existing_visitor_id = getattr(g, "analytics_visitor_id", None)
        if existing_visitor_id:
            return existing_visitor_id
        visitor_cookie = request.cookies.get(VISITOR_COOKIE)
        if not visitor_cookie:
            visitor_cookie = secrets.token_urlsafe(24)
            g.analytics_set_visitor_cookie = visitor_cookie
        visitor_id = hmac.new(
            current_app.secret_key.encode(),
            visitor_cookie.encode(),
            hashlib.sha256,
        ).hexdigest()
        g.analytics_visitor_id = visitor_id
        return visitor_id

    @classmethod
    def log(
        cls,
        *,
        event: str,
        path: str | None = None,
        method: str | None = None,
        status_code: int | None = None,
        recipe_id: int | None = None,
        duration_ms: int | None = None,
        error_type: str | None = None,
        referrer: str | None = None,
        metadata: dict[str, Any] | None = None,
        visitor_id: str | None = None,
    ) -> None:
        """Persist an event without allowing analytics failures to affect a request."""
        try:
            occurred_at = datetime.now(UTC)
            visitor_id = visitor_id or cls.visitor_id()
            user_id = (
                current_user.id
                if current_user.is_authenticated and current_user.is_active
                else None
            )
            db.session.add(
                AnalyticsEvent(
                    event_type=event,
                    occurred_at=occurred_at,
                    path=(path or request.path)[:500],
                    method=(method or request.method)[:10],
                    status_code=status_code,
                    recipe_id=recipe_id,
                    user_id=user_id,
                    visitor_id=visitor_id,
                    duration_ms=duration_ms,
                    error_type=error_type,
                    referrer=(referrer or request.referrer or "")[:500] or None,
                    metadata_json=metadata or {},
                )
            )
            if event in ROLLUP_EVENTS:
                cls._increment_daily(event, occurred_at.date(), recipe_id)
            if event in PAGE_VIEW_EVENTS:
                cls._record_daily_visitor(occurred_at.date(), visitor_id)
            if event == "error":
                cls._record_error_group(
                    occurred_at=occurred_at,
                    status_code=status_code,
                    path=(path or request.path)[:500],
                    method=(method or request.method)[:10],
                    error_type=error_type,
                    referrer=(referrer or request.referrer or "")[:500] or None,
                )
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Analytics event could not be stored")

    @staticmethod
    def _record_error_group(
        *,
        occurred_at: datetime,
        status_code: int | None,
        path: str,
        method: str,
        error_type: str | None,
        referrer: str | None,
    ) -> None:
        bucket_minutes = current_app.config["ANALYTICS_ERROR_BUCKET_MINUTES"]
        bucket_started_at = occurred_at.replace(
            minute=(occurred_at.minute // bucket_minutes) * bucket_minutes,
            second=0,
            microsecond=0,
        )
        group = (
            AnalyticsErrorGroup.query.filter_by(
                bucket_started_at=bucket_started_at,
                status_code=status_code,
                path=path,
                method=method,
                error_type=error_type,
                referrer=referrer,
            )
            .order_by(AnalyticsErrorGroup.last_occurred_at.desc())
            .first()
        )
        if group is not None:
            group.last_occurred_at = occurred_at
            group.occurrence_count += 1
            return
        db.session.add(
            AnalyticsErrorGroup(
                bucket_started_at=bucket_started_at,
                first_occurred_at=occurred_at,
                last_occurred_at=occurred_at,
                occurrence_count=1,
                status_code=status_code,
                path=path,
                method=method,
                error_type=error_type,
                referrer=referrer,
            )
        )

    @staticmethod
    def _increment_daily(event: str, day: date, recipe_id: int | None) -> None:
        daily = AnalyticsDaily.query.filter_by(
            day=day, event_type=event, recipe_id=recipe_id
        ).first()
        if daily is None:
            daily = AnalyticsDaily(
                day=day, event_type=event, recipe_id=recipe_id, event_count=0
            )
            db.session.add(daily)
        daily.event_count += 1

    @staticmethod
    def _record_daily_visitor(day: date, visitor_id: str) -> None:
        existing = AnalyticsDailyVisitor.query.filter_by(
            day=day, visitor_id=visitor_id
        ).first()
        if existing is None:
            db.session.add(AnalyticsDailyVisitor(day=day, visitor_id=visitor_id))

    @classmethod
    def record_request(cls, response) -> None:
        started = getattr(g, "analytics_started_at", None)
        duration_ms = (
            max(0, int((datetime.now(UTC) - started).total_seconds() * 1000))
            if started
            else None
        )
        is_public_page = (
            request.method == "GET"
            and 200 <= response.status_code < 300
            and response.content_type.startswith("text/html")
            and not request.path.startswith(("/admin", "/account", "/api", "/static"))
        )
        if is_public_page:
            cls.log(
                event=(
                    "recipe_view"
                    if request.endpoint == "recipes.view_recipe"
                    and getattr(g, "analytics_recipe_id", None)
                    else "page_view"
                ),
                status_code=response.status_code,
                duration_ms=duration_ms,
                recipe_id=getattr(g, "analytics_recipe_id", None),
            )
        cls.log(
            event="request",
            status_code=response.status_code,
            duration_ms=duration_ms,
            metadata={
                "slow": bool(
                    duration_ms
                    and duration_ms >= current_app.config["ANALYTICS_SLOW_REQUEST_MS"]
                )
            },
        )

    @classmethod
    def error(cls, error) -> None:
        cls.log(
            event="error",
            status_code=getattr(error, "code", None),
            error_type=type(error).__name__,
            duration_ms=cls._duration_ms(),
        )

    @staticmethod
    def _duration_ms() -> int | None:
        started = getattr(g, "analytics_started_at", None)
        if started is None:
            return None
        return max(0, int((datetime.now(UTC) - started).total_seconds() * 1000))

    @classmethod
    def summary(cls, days: int) -> dict[str, int]:
        since = datetime.now(UTC) - timedelta(days=days)
        page_views = AnalyticsEvent.query.filter(
            AnalyticsEvent.event_type.in_(PAGE_VIEW_EVENTS),
            AnalyticsEvent.occurred_at >= since,
        )
        return {
            "unique_visitors": db.session.query(
                func.count(func.distinct(AnalyticsEvent.visitor_id))
            )
            .filter(
                AnalyticsEvent.event_type.in_(PAGE_VIEW_EVENTS),
                AnalyticsEvent.occurred_at >= since,
            )
            .scalar()
            or 0,
            "page_views": page_views.count(),
            "authenticated_users": db.session.query(
                func.count(func.distinct(AnalyticsEvent.user_id))
            )
            .filter(
                AnalyticsEvent.event_type.in_(PAGE_VIEW_EVENTS),
                AnalyticsEvent.occurred_at >= since,
                AnalyticsEvent.user_id.isnot(None),
            )
            .scalar()
            or 0,
            "errors": AnalyticsEvent.query.filter(
                AnalyticsEvent.event_type == "error",
                AnalyticsEvent.occurred_at >= since,
            ).count(),
        }

    @classmethod
    def top_recipes(cls, days: int, limit: int = 10):
        since = datetime.now(UTC) - timedelta(days=days)
        return (
            db.session.query(Recipe, func.count(AnalyticsEvent.id).label("views"))
            .join(AnalyticsEvent, AnalyticsEvent.recipe_id == Recipe.id)
            .filter(
                AnalyticsEvent.event_type == "recipe_view",
                AnalyticsEvent.occurred_at >= since,
                Recipe.status == Recipe.STATUS_PUBLIC,
            )
            .group_by(Recipe.id)
            .order_by(func.count(AnalyticsEvent.id).desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def slow_routes(cls, days: int, limit: int = 10):
        since = datetime.now(UTC) - timedelta(days=days)
        return (
            db.session.query(
                AnalyticsEvent.path,
                func.count(AnalyticsEvent.id).label("requests"),
                func.avg(AnalyticsEvent.duration_ms).label("average_ms"),
                func.max(AnalyticsEvent.duration_ms).label("max_ms"),
            )
            .filter(
                AnalyticsEvent.event_type == "request",
                AnalyticsEvent.occurred_at >= since,
            )
            .group_by(AnalyticsEvent.path)
            .order_by(func.avg(AnalyticsEvent.duration_ms).desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def recent_errors(cls, days: int, limit: int = 25):
        since = datetime.now(UTC) - timedelta(days=days)
        return (
            AnalyticsErrorGroup.query.filter(
                AnalyticsErrorGroup.last_occurred_at >= since,
            )
            .order_by(AnalyticsErrorGroup.last_occurred_at.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def cleanup(cls, *, raw_days: int, daily_days: int) -> tuple[int, int]:
        raw_cutoff = datetime.now(UTC) - timedelta(days=raw_days)
        daily_cutoff = (datetime.now(UTC) - timedelta(days=daily_days)).date()
        raw_result = db.session.execute(
            delete(AnalyticsEvent).where(AnalyticsEvent.occurred_at < raw_cutoff)
        )
        db.session.execute(
            delete(AnalyticsDaily).where(AnalyticsDaily.day < daily_cutoff)
        )
        db.session.execute(
            delete(AnalyticsDailyVisitor).where(
                AnalyticsDailyVisitor.day < daily_cutoff
            )
        )
        db.session.execute(
            delete(AnalyticsErrorGroup).where(
                AnalyticsErrorGroup.last_occurred_at < raw_cutoff
            )
        )
        db.session.commit()
        return raw_result.rowcount or 0, daily_days
