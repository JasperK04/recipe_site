"""Add fixed bucket timestamps to grouped errors.

Revision ID: f2a1b0c9d8e7
Revises: e1f0a9b8c7d6
Create Date: 2026-09-21 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "f2a1b0c9d8e7"
down_revision = "e1f0a9b8c7d6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "analytics_error_groups",
        sa.Column("bucket_started_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_analytics_error_groups_bucket_started_at",
        "analytics_error_groups",
        ["bucket_started_at"],
    )
    connection = op.get_bind()
    groups = sa.table(
        "analytics_error_groups",
        sa.column("id", sa.Integer()),
        sa.column("first_occurred_at", sa.DateTime()),
        sa.column("bucket_started_at", sa.DateTime()),
    )
    for group_id, first_occurred_at in connection.execute(
        sa.select(groups.c.id, groups.c.first_occurred_at).where(
            groups.c.bucket_started_at.is_(None)
        )
    ):
        bucket_started_at = first_occurred_at.replace(
            minute=(first_occurred_at.minute // 15) * 15,
            second=0,
            microsecond=0,
        )
        connection.execute(
            groups.update()
            .where(groups.c.id == group_id)
            .values(bucket_started_at=bucket_started_at)
        )


def downgrade():
    op.drop_index(
        "ix_analytics_error_groups_bucket_started_at",
        table_name="analytics_error_groups",
    )
    op.drop_column("analytics_error_groups", "bucket_started_at")
