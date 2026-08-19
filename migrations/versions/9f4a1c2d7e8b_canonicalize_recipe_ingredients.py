"""canonicalize recipe ingredient JSON

Revision ID: 9f4a1c2d7e8b
Revises: 4332bb8ecf71
Create Date: 2026-08-19

"""

import json

import sqlalchemy as sa
from alembic import op

revision = "9f4a1c2d7e8b"
down_revision = "4332bb8ecf71"
branch_labels = None
depends_on = None


def _decode(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _upgrade_ingredient(ingredient):
    if not isinstance(ingredient, dict):
        return ingredient
    if ingredient.get("type") == "recipe":
        return ingredient
    name = (
        ingredient.get("display_name")
        or ingredient.get("name")
        or ingredient.get("name_")
    )
    if not name:
        return ingredient
    return {
        "type": "ingredient",
        "display_name": str(name).strip(),
        "quantity": ingredient.get("quantity"),
        "unit": str(
            ingredient.get("unit")
            if ingredient.get("unit") is not None
            else ingredient.get("measurement") or ""
        ).strip(),
    }


def _downgrade_ingredient(ingredient):
    if not isinstance(ingredient, dict) or ingredient.get("type") != "ingredient":
        return ingredient
    return {
        "name": ingredient.get("display_name", ""),
        "quantity": ingredient.get("quantity"),
        "measurement": ingredient.get("unit", ""),
    }


def _convert_rows(converter):
    recipes = sa.table("recipes", sa.column("id"), sa.column("ingredients"))
    connection = op.get_bind()
    rows = connection.execute(sa.select(recipes.c.id, recipes.c.ingredients)).fetchall()
    for recipe_id, raw_ingredients in rows:
        ingredients = _decode(raw_ingredients)
        if not isinstance(ingredients, list):
            continue
        converted = [converter(ingredient) for ingredient in ingredients]
        if converted != ingredients:
            connection.execute(
                recipes.update()
                .where(recipes.c.id == recipe_id)
                .values(ingredients=json.dumps(converted))
            )


def upgrade():
    _convert_rows(_upgrade_ingredient)


def downgrade():
    _convert_rows(_downgrade_ingredient)
