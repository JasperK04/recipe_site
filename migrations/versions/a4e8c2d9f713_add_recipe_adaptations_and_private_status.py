"""Add standalone recipe adaptations and replace draft with private.

Revision ID: a4e8c2d9f713
Revises: f1a2b3c4d5e6
Create Date: 2026-09-20 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "a4e8c2d9f713"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE recipes SET status = 'private' WHERE status = 'draft'")
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("original_recipe_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_recipes_original_recipe",
            "recipes",
            ["original_recipe_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint(
            "uq_recipes_user_original_recipe", ["user_id", "original_recipe_id"]
        )


def downgrade():
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        batch_op.drop_constraint("uq_recipes_user_original_recipe", type_="unique")
        batch_op.drop_constraint("fk_recipes_original_recipe", type_="foreignkey")
        batch_op.drop_column("original_recipe_id")
    op.execute("UPDATE recipes SET status = 'draft' WHERE status = 'private'")
