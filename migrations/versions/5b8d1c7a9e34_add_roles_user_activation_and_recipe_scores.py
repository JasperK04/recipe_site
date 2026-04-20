"""Add roles, user activation, and recipe scores

Revision ID: 5b8d1c7a9e34
Revises: d2f8ee6cee38
Create Date: 2026-04-20 20:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5b8d1c7a9e34"
down_revision = "d2f8ee6cee38"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "role",
                sa.String(length=20),
                nullable=False,
                server_default="reviewer",
            )
        )
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column(
                "creator_request_pending",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.create_index(batch_op.f("ix_users_role"), ["role"], unique=False)

    # Keep existing bootstrap admin users as admin after migration.
    op.execute(
        sa.text(
            "UPDATE users SET role = 'admin' WHERE lower(username) = 'admin' OR lower(email) = 'admin@example.com'"
        )
    )

    with op.batch_alter_table("recipes", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("status_before_deactivation", sa.String(length=20), nullable=True)
        )

    op.create_table(
        "recipe_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("score >= 1 AND score <= 5", name="ck_recipe_scores_score"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_id", "user_id", name="uq_recipe_scores_recipe_user"),
    )


def downgrade():
    op.drop_table("recipe_scores")

    with op.batch_alter_table("recipes", schema=None) as batch_op:
        batch_op.drop_column("status_before_deactivation")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_role"))
        batch_op.drop_column("creator_request_pending")
        batch_op.drop_column("is_active")
        batch_op.drop_column("role")
