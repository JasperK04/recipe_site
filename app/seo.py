from __future__ import annotations

from collections.abc import Iterable

from app.models import Recipe
from utils import ingredient_to_string


def recipe_description(recipe: Recipe) -> str:
    description = " ".join((recipe.description or "").split())
    if description:
        return description[:160].rstrip()
    category = f"{recipe.category.lower()} " if recipe.category else ""
    return f"Bekijk dit {category}recept van {recipe.author.username}: {recipe.title}."


def recipe_duration(minutes: int | None) -> str | None:
    if minutes is None or minutes < 0:
        return None
    return f"PT{minutes}M"


def _recipe_ingredients(ingredients: Iterable[str | dict] | None) -> list[str]:
    values = []
    for ingredient in ingredients or []:
        value = (
            ingredient_to_string(ingredient)
            if isinstance(ingredient, dict)
            else ingredient
        )
        if value:
            values.append(str(value))
    return values


def recipe_schema(recipe: Recipe, *, url: str, image_url: str | None) -> dict:
    schema = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": recipe.title,
        "description": recipe_description(recipe),
        "url": url,
        "author": {"@type": "Person", "name": recipe.author.username},
        "recipeIngredient": _recipe_ingredients(recipe.ingredients),
        "recipeInstructions": [
            {"@type": "HowToStep", "text": str(instruction)}
            for instruction in (recipe.instructions or [])
            if str(instruction).strip()
        ],
    }
    if image_url:
        schema["image"] = image_url
    if recipe.prep_time is not None:
        schema["prepTime"] = recipe_duration(recipe.prep_time)
    if recipe.cook_time is not None:
        schema["cookTime"] = recipe_duration(recipe.cook_time)
    if recipe.prep_time is not None and recipe.cook_time is not None:
        schema["totalTime"] = recipe_duration(recipe.prep_time + recipe.cook_time)
    if recipe.servings is not None:
        schema["recipeYield"] = str(recipe.servings)
    if recipe.category:
        schema["recipeCategory"] = recipe.category
    return schema
