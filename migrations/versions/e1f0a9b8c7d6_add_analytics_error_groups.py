"""Add grouped error analytics.

Revision ID: e1f0a9b8c7d6
Revises: d9e8f7a6b5c4
Create Date: 2026-09-21 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "e1f0a9b8c7d6"
down_revision = "d9e8f7a6b5c4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analytics_error_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_occurred_at", sa.DateTime(), nullable=False),
        sa.Column("last_occurred_at", sa.DateTime(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("error_type", sa.String(length=120), nullable=True),
        sa.Column("referrer", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analytics_error_groups_first_occurred_at",
        "analytics_error_groups",
        ["first_occurred_at"],
    )
    op.create_index(
        "ix_analytics_error_groups_last_occurred_at",
        "analytics_error_groups",
        ["last_occurred_at"],
    )


def downgrade():
    op.drop_table("analytics_error_groups")
