"""Drop user_machines table

Revision ID: a2b3c4d5e6f7
Revises: fd61f64e663c
Create Date: 2026-04-13 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a2b3c4d5e6f7"
down_revision = "fd61f64e663c"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the user_machines association table; users are no longer linked to machines
    op.drop_table("user_machines")


def downgrade():
    # Recreate user_machines table in case of downgrade
    op.create_table(
        "user_machines",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["kitchen_machines.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("user_id", "machine_id"),
    )
