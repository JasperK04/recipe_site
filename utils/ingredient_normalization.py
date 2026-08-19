"""Configuration-driven ingredient unit normalization."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "ingredient_normalization.json"
)


def _config_path() -> Path:
    """Return the configured unit-normalization file path."""
    return Path(os.environ.get("INGREDIENT_NORMALIZATION_FILE", DEFAULT_CONFIG_PATH))


@lru_cache(maxsize=1)
def _load_unit_rules(path: str) -> dict[str, tuple[str | None, float]]:
    """Load aliases from the JSON configuration file.

    A unit may be written as a string (``"gram": "g"``) or as an object when
    the amount must also be converted (``"kg": {"unit": "g", "multiplier": 1000}``).
    """
    with Path(path).open(encoding="utf-8") as config_file:
        raw_rules = json.load(config_file).get("units", {})

    if not isinstance(raw_rules, dict):
        raise TypeError("ingredient normalization config 'units' must be an object")

    rules: dict[str, tuple[str, float]] = {}
    for alias, value in raw_rules.items():
        if not isinstance(alias, str):
            raise TypeError("ingredient normalization unit aliases must be strings")
        if isinstance(value, str):
            unit, multiplier = value, 1
        elif isinstance(value, dict):
            unit = value.get("unit")
            multiplier = value.get("multiplier", 1)
        else:
            raise TypeError(f"invalid normalization rule for unit {alias!r}")
        if not isinstance(unit, str):
            raise TypeError(f"normalization rule for unit {alias!r} needs a unit")
        if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool):
            raise TypeError(
                f"normalization rule for unit {alias!r} has an invalid multiplier"
            )
        # An empty target unit intentionally means a countable ingredient: for
        # example, ``2 st eieren`` becomes ``2 eieren`` without a measurement.
        rules[alias.strip().casefold()] = (unit.strip() or None, float(multiplier))  # type: ignore[assignment]
    return rules  # type: ignore


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
    from utils.general import parse_ingredient

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
                    "unit": ingredient.get("unit") or ingredient.get("measurement") or "",
                }
            )
            continue

        name = ingredient.get("display_name") or ingredient.get("name") or ingredient.get("name_")
        if not name:
            continue
        quantity = ingredient.get("quantity")
        unit, multiplier = normalize_unit(
            ingredient.get("unit") or ingredient.get("measurement")
        )
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
