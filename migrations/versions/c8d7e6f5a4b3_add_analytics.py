"""Add centralized analytics event and daily rollup tables.

Revision ID: c8d7e6f5a4b3
Revises: a4e8c2d9f713
Create Date: 2026-09-21 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "c8d7e6f5a4b3"
down_revision = "a4e8c2d9f713"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("recipe_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("visitor_id", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(length=120), nullable=True),
        sa.Column("referrer", sa.String(length=500), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("event_type", "event_type"),
        ("occurred_at", "occurred_at"),
        ("recipe_id", "recipe_id"),
        ("user_id", "user_id"),
        ("visitor_id", "visitor_id"),
    ):
        op.create_index(f"ix_analytics_events_{name}", "analytics_events", [column])

    op.create_table(
        "analytics_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "day", "event_type", "recipe_id", name="uq_analytics_daily_event"
        ),
    )
    op.create_index("ix_analytics_daily_day", "analytics_daily", ["day"])
    op.create_index("ix_analytics_daily_recipe_id", "analytics_daily", ["recipe_id"])

    op.create_table(
        "analytics_daily_visitors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("visitor_id", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day", "visitor_id", name="uq_analytics_daily_visitor"),
    )
    op.create_index(
        "ix_analytics_daily_visitors_day", "analytics_daily_visitors", ["day"]
    )
    op.create_index(
        "ix_analytics_daily_visitors_visitor_id",
        "analytics_daily_visitors",
        ["visitor_id"],
    )


def downgrade():
    op.drop_table("analytics_daily_visitors")
    op.drop_table("analytics_daily")
    op.drop_table("analytics_events")
