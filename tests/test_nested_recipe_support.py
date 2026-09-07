from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.models import Recipe
from app.services.nested_recipes import (
    find_recipes_referencing_recipe,
    validate_nested_recipe_reference,
    validate_recipe_dependency_graph,
)
from utils import sanitize_recipe_ingredients


class NestedRecipeSupportTests(unittest.TestCase):
    def test_recipe_form_restores_nested_recipe_json_on_submit(self):
        template = Path("app/templates/recipes/form.html").read_text()

        self.assertIn(
            "const ingredientForm = document.getElementById('recipe-form');",
            template,
        )
        self.assertIn("input.value = input.dataset.rawIngredientJson;", template)

    def test_recipe_form_clears_stale_nested_recipe_state(self):
        template = Path("app/templates/recipes/form.html").read_text()

        self.assertIn("function resetIngredientItem(item)", template)
        self.assertIn("delete input.dataset.rawIngredientJson;", template)
        self.assertIn("resetIngredientItem(clone);", template)
        self.assertIn("resetIngredientItem(empty);", template)
        self.assertIn("list.addEventListener('input'", template)
        self.assertIn(
            "input.matches('input, textarea, select') && input.value.trim() === ''",
            template,
        )
        self.assertIn("input.closest('.ingredient-item')?.classList.remove('has-imported-recipe');", template)

    def test_normal_ingredients_stay_unchanged(self):
        ingredient = {"name": "tomaat", "quantity": 2, "unit": ""}
        self.assertEqual(validate_nested_recipe_reference(ingredient), ingredient)

    def test_nested_recipe_reference_validates(self):
        ingredient = {
            "type": "recipe",
            "recipe_id": 42,
            "display_name": "Tomatensaus",
            "quantity": 1,
            "unit": "portie",
        }
        self.assertEqual(validate_nested_recipe_reference(ingredient), ingredient)

    def test_nested_recipe_quantity_is_stored_as_a_number(self):
        ingredient = {
            "type": "recipe",
            "recipe_id": 42,
            "display_name": "Tomatensaus",
            "quantity": "1.5",
            "unit": "portie",
        }

        normalized = validate_nested_recipe_reference(ingredient)

        self.assertEqual(normalized["quantity"], 1.5)
        self.assertIsInstance(normalized["quantity"], float)

    def test_imported_nested_recipe_json_is_normalized_for_storage(self):
        raw_ingredient = json.dumps(
            {
                "type": "recipe",
                "recipe_id": 42,
                "display_name": "Tomatensaus",
                "quantity": "1",
                "unit": "portie",
            }
        )

        self.assertEqual(
            sanitize_recipe_ingredients([raw_ingredient]),
            [
                {
                    "type": "recipe",
                    "recipe_id": 42,
                    "display_name": "Tomatensaus",
                    "quantity": 1,
                    "unit": "portie",
                }
            ],
        )

    def test_nested_recipe_reference_rejects_self_reference(self):
        ingredient = {
            "type": "recipe",
            "recipe_id": 7,
            "display_name": "Zelf",
            "quantity": 1,
            "unit": "portie",
        }
        with self.assertRaises(ValueError):
            validate_nested_recipe_reference(ingredient, recipe_id=7)

    def test_dependency_graph_rejects_direct_and_indirect_cycles(self):
        graph = {
            1: [2],
            2: [3],
            3: [1],
        }
        with self.assertRaises(ValueError):
            validate_recipe_dependency_graph(1, graph)

        graph = {1: [2], 2: [1]}
        with self.assertRaises(ValueError):
            validate_recipe_dependency_graph(1, graph)

    def test_find_recipes_referencing_recipe(self):
        recipes = [
            Recipe(
                id=1,
                title="A",
                ingredients=[
                    {
                        "type": "recipe",
                        "recipe_id": 99,
                        "display_name": "B",
                        "quantity": 1,
                        "unit": "portie",
                    }
                ],
                instructions=[],
                user_id=1,
            ),
            Recipe(
                id=2,
                title="B",
                ingredients=[
                    {
                        "type": "recipe",
                        "recipe_id": 100,
                        "display_name": "C",
                        "quantity": 1,
                        "unit": "portie",
                    }
                ],
                instructions=[],
                user_id=1,
            ),
            Recipe(
                id=3,
                title="C",
                ingredients=[
                    {
                        "type": "recipe",
                        "recipe_id": 99,
                        "display_name": "B",
                        "quantity": 1,
                        "unit": "portie",
                    }
                ],
                instructions=[],
                user_id=1,
            ),
        ]
        self.assertEqual(
            [recipe.id for recipe in find_recipes_referencing_recipe(99, recipes)],
            [1, 3],
        )


if __name__ == "__main__":
    unittest.main()
