"""Add secure password-reset fields to OTC records.

Revision ID: e4f6a8b0c2d4
Revises: 9f4a1c2d7e8b
Create Date: 2026-08-28 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "e4f6a8b0c2d4"
down_revision = "9f4a1c2d7e8b"
branch_labels = None
depends_on = None


def upgrade():
    # batch mode also supports SQLite, the application's default database.
    with op.batch_alter_table("otc") as batch_op:
        batch_op.add_column(
            sa.Column("token_hash", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("used_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_otc_token_hash", ["token_hash"], unique=True)
        batch_op.create_index("ix_otc_user_id", ["user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_otc_user_id_users", "users", ["user_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("otc") as batch_op:
        batch_op.drop_constraint("fk_otc_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_otc_user_id")
        batch_op.drop_index("ix_otc_token_hash")
        batch_op.drop_column("used_at")
        batch_op.drop_column("user_id")
        batch_op.drop_column("token_hash")
