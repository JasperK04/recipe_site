"""Add indexed reverse tags for nested recipe dependencies.

Revision ID: b5c6d7e8f901
Revises: a4e8c2d9f713
Create Date: 2026-09-20 00:00:00.000000
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "b5c6d7e8f901"
down_revision = "a4e8c2d9f713"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recipe_dependencies",
        sa.Column("dependent_recipe_id", sa.Integer(), nullable=False),
        sa.Column("dependency_recipe_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dependent_recipe_id"], ["recipes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dependency_recipe_id"], ["recipes.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("dependent_recipe_id", "dependency_recipe_id"),
        sa.UniqueConstraint(
            "dependent_recipe_id",
            "dependency_recipe_id",
            name="uq_recipe_dependencies_edge",
        ),
    )

    recipes = sa.table("recipes", sa.column("id"), sa.column("ingredients"))
    dependencies = sa.table(
        "recipe_dependencies",
        sa.column("dependent_recipe_id"),
        sa.column("dependency_recipe_id"),
    )

    connection = op.get_bind()
    rows = connection.execute(
        sa.select(recipes.c.id, recipes.c.ingredients)
    ).fetchall()

    for recipe_id, raw_ingredients in rows:
        if isinstance(raw_ingredients, str):
            try:
                raw_ingredients = json.loads(raw_ingredients)
            except json.JSONDecodeError:
                continue

        if not isinstance(raw_ingredients, list):
            continue

        dependency_ids = {
            ingredient.get("recipe_id")
            for ingredient in raw_ingredients
            if isinstance(ingredient, dict)
            and ingredient.get("type") == "recipe"
            and isinstance(ingredient.get("recipe_id"), int)
            and ingredient.get("recipe_id") != recipe_id
        }

        if dependency_ids:
            connection.execute(
                dependencies.insert(),
                [
                    {
                        "dependent_recipe_id": recipe_id,
                        "dependency_recipe_id": dependency_id,
                    }
                    for dependency_id in dependency_ids
                ],
            )


def downgrade():
    op.drop_table("recipe_dependencies")
