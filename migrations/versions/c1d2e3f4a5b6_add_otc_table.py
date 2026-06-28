"""Add OTC table for registration invites

Revision ID: c1d2e3f4a5b6
Revises: b7f9d24a1c3e
Create Date: 2026-06-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b6"
down_revision = "b7f9d24a1c3e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "otc",
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_otc_expires_at", "otc", ["expires_at"], unique=False)


def downgrade():
    op.drop_index("ix_otc_expires_at", table_name="otc")
    op.drop_table("otc")
