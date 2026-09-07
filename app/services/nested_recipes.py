from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from flask import has_app_context

from app.models import Recipe


def _coerce_recipe_id(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.isdigit():
            parsed = int(candidate)
            return parsed if parsed > 0 else None
        if candidate.startswith(("http://", "https://")):
            return None
        return None
    return None


def _is_external_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return bool(re.match(r"^https?://", value.strip(), flags=re.IGNORECASE))


def _normalize_nested_ingredient(
    ingredient: dict[str, Any], *, recipe_id: int | None = None
) -> dict[str, Any]:
    if not isinstance(ingredient, dict):
        raise TypeError("Nested recipe ingredient must be an object.")

    if ingredient.get("type") != "recipe":
        return ingredient

    normalized_recipe_id = _coerce_recipe_id(ingredient.get("recipe_id"))
    if normalized_recipe_id is None:
        raise ValueError(
            "Nested recipe references must use a valid internal recipe ID."
        )

    if recipe_id is not None and normalized_recipe_id == recipe_id:
        raise ValueError("Een recept kan niet naar zichzelf verwijzen.")

    if _is_external_url(ingredient.get("recipe_id")) or any(
        _is_external_url(value)
        for value in ingredient.values()
        if isinstance(value, str)
    ):
        raise ValueError(
            "Externe URLs zijn niet toegestaan als nested recipe reference."
        )

    display_name = str(ingredient.get("display_name") or "").strip()
    if not display_name:
        raise ValueError("Een nested recipe ingredient heeft een weergavenaam nodig.")

    quantity = ingredient.get("quantity")
    if quantity in (None, ""):
        raise ValueError("Bij een nested recipe ingredient is een hoeveelheid vereist.")
    try:
        numeric_quantity = float(quantity)
    except (TypeError, ValueError):
        raise ValueError(
            "Bij een nested recipe ingredient is een geldige hoeveelheid vereist."
        ) from None
    if numeric_quantity.is_integer():
        numeric_quantity = int(numeric_quantity)

    unit = str(ingredient.get("unit") or "").strip()

    if has_app_context():
        existing_recipe = Recipe.query.filter(
            Recipe.id == normalized_recipe_id,
            Recipe.status != Recipe.STATUS_DEACTIVATED,
        ).first()
        if existing_recipe is None:
            raise ValueError("Het geselecteerde recept bestaat niet meer.")

    return {
        "type": "recipe",
        "recipe_id": normalized_recipe_id,
        "display_name": display_name,
        "quantity": numeric_quantity,
        "unit": unit,
    }


def validate_nested_recipe_reference(
    ingredient: Any, *, recipe_id: int | None = None
) -> Any:
    if not isinstance(ingredient, dict):
        return ingredient
    if ingredient.get("type") != "recipe":
        return ingredient
    return _normalize_nested_ingredient(ingredient, recipe_id=recipe_id)


def nested_recipe_dependency_ids(recipe: Recipe) -> list[int]:
    ids: list[int] = []
    for ingredient in recipe.ingredients or []:
        if isinstance(ingredient, dict) and ingredient.get("type") == "recipe":
            recipe_id = _coerce_recipe_id(ingredient.get("recipe_id"))
            if recipe_id is not None:
                ids.append(recipe_id)
    return ids


def build_recipe_dependency_graph(recipes: Iterable[Recipe]) -> dict[int, list[int]]:
    graph: dict[int, list[int]] = {}
    for recipe in recipes:
        graph[recipe.id] = nested_recipe_dependency_ids(recipe)
    return graph


def validate_recipe_dependency_graph(
    recipe_id: int, graph: dict[int, list[int]]
) -> None:
    visited: set[int] = set()
    stack: list[int] = []

    def visit(node: int) -> None:
        if node in stack:
            raise ValueError("Circular nested recipe dependency detected.")
        if node in visited:
            return
        stack.append(node)
        for dependency in graph.get(node, []):
            if dependency == recipe_id and node == recipe_id:
                raise ValueError("Een recept kan niet naar zichzelf verwijzen.")
            if dependency in graph:
                visit(dependency)
        stack.pop()
        visited.add(node)

    visit(recipe_id)


def resolve_recipe_reference(value: str | int) -> Recipe:
    if value is None:
        raise ValueError("Geen recept geselecteerd.")

    if isinstance(value, int):
        recipe = Recipe.query.filter_by(id=value).first()
        if recipe is None:
            raise ValueError(f"Recept met ID {value} bestaat niet.")
        return recipe

    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError("Geen recept geselecteerd.")

    if cleaned.isdigit():
        recipe = Recipe.query.filter_by(id=int(cleaned)).first()
        if recipe is None:
            raise ValueError(f"Recept met ID {int(cleaned)} bestaat niet.")
        return recipe

    matches = Recipe.query.filter(
        Recipe.title.ilike(cleaned), Recipe.status != Recipe.STATUS_DEACTIVATED
    ).all()
    if not matches:
        raise ValueError(f"Recept met titel '{cleaned}' kon niet worden gevonden.")
    if len(matches) > 1:
        raise ValueError(
            f"Titel '{cleaned}' is niet uniek. Kies een specifiek recept ID."
        )
    return matches[0]


def find_recipes_referencing_recipe(
    recipe_id: int, recipes: Iterable[Recipe] | None = None
) -> list[Recipe]:
    candidates = recipes if recipes is not None else Recipe.query.all()
    matches: list[Recipe] = []
    for recipe in candidates:
        for ingredient in recipe.ingredients or []:
            if isinstance(ingredient, dict) and ingredient.get("type") == "recipe":
                candidate_id = _coerce_recipe_id(ingredient.get("recipe_id"))
                if candidate_id == recipe_id:
                    matches.append(recipe)
                    break
    return matches


def remove_deleted_nested_recipe_reference(
    ingredient: Any, deleted_recipe_id: int
) -> Any:
    if not isinstance(ingredient, dict) or ingredient.get("type") != "recipe":
        return ingredient
    if _coerce_recipe_id(ingredient.get("recipe_id")) != deleted_recipe_id:
        return ingredient

    display_name = (
        str(ingredient.get("display_name") or "Verwijderd recept").strip()
        or "Verwijderd recept"
    )
    quantity = ingredient.get("quantity")
    unit = str(ingredient.get("unit") or "").strip()
    cleaned: dict[str, Any] = {
        "name": display_name,
        "quantity": quantity,
        "unit": unit or None,
    }
    if quantity in (None, ""):
        cleaned.pop("quantity", None)
    if not cleaned["unit"]:
        cleaned.pop("unit", None)
    return cleaned


def sanitize_nested_recipe_ingredients(raw_ingredients: Any) -> list[dict[str, Any]]:
    if raw_ingredients is None:
        return []

    ingredients: list[dict[str, Any]] = []
    for ingredient in raw_ingredients:
        if isinstance(ingredient, dict) and ingredient.get("type") == "recipe":
            ingredients.append(validate_nested_recipe_reference(ingredient))
        elif isinstance(ingredient, dict):
            ingredients.append(ingredient)
    return ingredients


def resolve_recipe_search_term(term: str) -> list[Recipe]:
    cleaned = (term or "").strip()
    if not cleaned:
        return []

    query = Recipe.query.filter(Recipe.status != Recipe.STATUS_DEACTIVATED)
    if cleaned.isdigit():
        return query.filter(Recipe.id == int(cleaned)).limit(6).all()

    exact_matches = (
        query.filter(Recipe.title.ilike(cleaned)).order_by(Recipe.title.asc()).all()
    )
    if len(exact_matches) == 1:
        return exact_matches

    pattern = f"%{cleaned}%"
    return (
        query.filter(Recipe.title.ilike(pattern))
        .order_by(Recipe.title.asc())
        .limit(6)
        .all()
    )


def handle_referenced_recipe_update(recipe: Recipe) -> list[Recipe]:
    referencing_recipes = find_recipes_referencing_recipe(recipe.id)
    return referencing_recipes


def handle_referenced_recipe_deletion(recipe: Recipe) -> list[Recipe]:
    referencing_recipes = find_recipes_referencing_recipe(recipe.id)
    if not referencing_recipes:
        return []

    for dependent in referencing_recipes:
        dependent.status = Recipe.STATUS_DRAFT
        dependent.moderation_status = "allowed"
        dependent.moderation_issues = []
        dependent.status_before_moderation = None
        dependent.moderation_notification_signature = None
    return referencing_recipes
