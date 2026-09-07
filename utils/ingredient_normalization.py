"""Configuration-driven ingredient unit normalization."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from utils.general import parse_ingredient

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "ingredient_normalization.json"
)


def _config_path() -> Path:
    """Return the configured unit-normalization file path."""
    return Path(os.environ.get("INGREDIENT_NORMALIZATION_FILE", DEFAULT_CONFIG_PATH))


@lru_cache(maxsize=1)
def _load_unit_rules(path: str) -> dict[str, tuple[str | None, float]]:
    """Load a direct, case-insensitive alias lookup from the configuration."""
    with Path(path).open(encoding="utf-8") as config_file:
        raw_rules = json.load(config_file).get("units", {})

    if not isinstance(raw_rules, dict):
        raise TypeError("ingredient normalization config 'units' must be an object")

    rules: dict[str, tuple[str | None, float]] = {}

    def add_rule(alias: str, unit: str | None, multiplier: object, source: str) -> None:
        if not isinstance(alias, str):
            raise TypeError("ingredient normalization unit aliases must be strings")
        if unit is not None and not isinstance(unit, str):
            raise TypeError(f"normalization rule for unit {source!r} needs a unit")
        if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool):
            raise TypeError(
                f"normalization rule for unit {source!r} has an invalid multiplier"
            )
        normalized_alias = alias.strip().casefold()
        if normalized_alias:
            rules[normalized_alias] = (
                unit.strip() if unit else None,
                float(multiplier),
            )

    for canonical, value in raw_rules.items():
        if not isinstance(canonical, str):
            raise TypeError("ingredient normalization unit names must be strings")
        if isinstance(value, str):
            add_rule(canonical, value, 1, canonical)
            continue
        if not isinstance(value, dict):
            raise TypeError(f"invalid normalization rule for unit {canonical!r}")
        if "aliases" not in value:
            add_rule(
                canonical, value.get("unit"), value.get("multiplier", 1), canonical
            )
            continue

        aliases = value["aliases"]
        if not isinstance(aliases, list) or not all(
            isinstance(alias, str) for alias in aliases
        ):
            raise TypeError(
                f"normalization aliases for unit {canonical!r} must be a list"
            )
        self_unit = canonical == "it_self"
        target = None if canonical == "" else canonical
        for alias in aliases:
            add_rule(alias, alias if self_unit else target, 1, canonical)

        conversions = value.get("conversions", {})
        if not isinstance(conversions, dict):
            raise TypeError(
                f"normalization conversions for unit {canonical!r} must be an object"
            )
        for alias, multiplier in conversions.items():
            add_rule(alias, target, multiplier, canonical)

    return rules


def normalize_unit(unit: str | None) -> tuple[str | None, float]:
    """Return the canonical unit and quantity multiplier for a unit alias."""
    if not unit:
        return None, 1
    normalized = str(unit).strip().rstrip(".,;:").casefold()
    if not normalized:
        return None, 1
    return _load_unit_rules(str(_config_path())).get(normalized, (normalized, 1))


def is_configured_unit(unit: str | None) -> bool:
    """Return whether a unit is explicitly present in the normalization config."""
    if not unit:
        return False
    normalized = str(unit).strip().rstrip(".,;:").casefold()
    return bool(normalized) and normalized in _load_unit_rules(str(_config_path()))


def reload_unit_normalization() -> None:
    """Clear the config cache, primarily useful to long-running processes."""
    _load_unit_rules.cache_clear()


def normalize_stored_ingredients(ingredients: object) -> list[dict[str, Any]]:
    """Apply unit rules to recipe ingredients already stored in the database."""

    normalized: list[dict[str, Any]] = []
    for ingredient in ingredients or []:  # type: ignore
        if isinstance(ingredient, str):
            quantity, unit, name = parse_ingredient(ingredient)
            if name:
                normalized.append(
                    {
                        "type": "ingredient",
                        "display_name": name,
                        "quantity": quantity,
                        "unit": unit or "",
                    }
                )
            continue
        if not isinstance(ingredient, dict):
            continue

        if ingredient.get("type") == "recipe":
            normalized.append(
                {
                    "type": "recipe",
                    "recipe_id": ingredient.get("recipe_id"),
                    "display_name": ingredient.get("display_name")
                    or ingredient.get("name")
                    or "Recept",
                    "quantity": ingredient.get("quantity"),
                    "unit": ingredient.get("unit") or "",
                }
            )
            continue

        name = (
            ingredient.get("display_name")
            or ingredient.get("name")
            or ingredient.get("name_")
        )
        if not name:
            continue
        quantity = ingredient.get("quantity")
        if (
            isinstance(quantity, (int, float))
            and not isinstance(quantity, bool)
            and ingredient.get("unit")
        ):
            quantity, unit, name = parse_ingredient(
                f"{quantity} {ingredient['unit']} {name}"
            )
            normalized.append(
                {
                    "type": "ingredient",
                    "display_name": name,
                    "quantity": quantity,
                    "unit": unit or "",
                }
            )
            continue
        unit, multiplier = normalize_unit(ingredient.get("unit"))
        if isinstance(quantity, (int, float)) and not isinstance(quantity, bool):
            quantity *= multiplier
            if isinstance(quantity, float) and quantity.is_integer():
                quantity = int(quantity)
        normalized.append(
            {
                "type": "ingredient",
                "display_name": str(name),
                "quantity": quantity,
                "unit": unit or "",
            }
        )
    return normalized
