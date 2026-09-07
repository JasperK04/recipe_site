from __future__ import annotations

import json
import unittest
from pathlib import Path

import pytest

import app.api.recipes as recipes_api
from app import create_app, db
from app.api.common import ApiError
from app.api.recipes import create_recipe, update_recipe
from app.forms import RecipeForm
from app.models import Recipe, User
from app.services.nested_recipes import (
    find_recipes_referencing_recipe,
    validate_nested_recipe_reference,
    validate_recipe_dependency_graph,
)
from config import DevelopmentConfig, config
from utils import sanitize_recipe_ingredients


class NestedRecipeTestConfig(DevelopmentConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setitem(config, "nested_recipe_test", NestedRecipeTestConfig)
    application = create_app("nested_recipe_test")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


class NestedRecipeSupportTests(unittest.TestCase):
    def test_recipe_form_restores_nested_recipe_json_on_submit(self):
        validation_script = Path("app/static/js/validation.js").read_text()

        self.assertIn(
            "formData.set(input.name, input.dataset.rawIngredientJson);",
            validation_script,
        )

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
        self.assertIn(
            "input.closest('.ingredient-item')?.classList.remove('has-imported-recipe');",
            template,
        )

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


@pytest.mark.parametrize("status", [Recipe.STATUS_DRAFT, Recipe.STATUS_PUBLIC])
@pytest.mark.parametrize("operation", ["create", "update"])
def test_deleted_nested_recipe_rejects_create_and_update(app, status, operation):
    with app.app_context():
        author = User(
            username=f"chef-{operation}-{status}",
            email=f"{operation}-{status}@example.test",
        )
        author.set_password("password")
        db.session.add(author)
        db.session.commit()

        stale_ingredient = json.dumps(
            {
                "type": "recipe",
                "recipe_id": 999,
                "display_name": "Verwijderd recept",
                "quantity": 1,
                "unit": "portie",
            }
        )

        if operation == "create":
            with pytest.raises(ApiError):
                create_recipe(
                    author=author,
                    title="Nieuw recept",
                    description=None,
                    ingredients=[stale_ingredient],
                    instructions=["Roer."],
                    prep_time=None,
                    cook_time=None,
                    servings=2,
                    category=None,
                    status=status,
                )
            assert Recipe.query.count() == 0
        else:
            recipe = Recipe(
                title="Bestaand recept",
                ingredients=["1 tomaat"],
                instructions=["Snijd."],
                user_id=author.id,
                status=Recipe.STATUS_DRAFT,
            )
            db.session.add(recipe)
            db.session.commit()

            with pytest.raises(ApiError):
                update_recipe(
                    recipe=recipe,
                    title=recipe.title,
                    description=None,
                    ingredients=[stale_ingredient],
                    instructions=recipe.instructions,
                    prep_time=None,
                    cook_time=None,
                    servings=2,
                    category=None,
                    status=status,
                )

            db.session.expire_all()
            saved = db.session.get(Recipe, recipe.id)
            assert saved.ingredients == ["1 tomaat"]
            assert saved.status == Recipe.STATUS_DRAFT


def test_deactivated_nested_recipe_rejects_save(app):
    with app.app_context():
        author = User(
            username="chef-deactivated",
            email="deactivated@example.test",
        )
        author.set_password("password")
        db.session.add(author)
        db.session.commit()
        deactivated = Recipe(
            title="Niet beschikbaar",
            ingredients=["1 tomaat"],
            instructions=["Snijd."],
            user_id=author.id,
            status=Recipe.STATUS_DEACTIVATED,
        )
        db.session.add(deactivated)
        db.session.commit()

        ingredient = {
            "type": "recipe",
            "recipe_id": deactivated.id,
            "display_name": deactivated.title,
            "quantity": 1,
            "unit": "portie",
        }

        with pytest.raises(ValueError, match="bestaat niet meer"):
            validate_nested_recipe_reference(ingredient)


def test_updating_nested_recipe_notifies_referencing_recipe_owner(app, monkeypatch):
    with app.app_context():
        referenced_author = User(
            username="referenced-author",
            email="referenced@example.test",
        )
        parent_author = User(
            username="parent-author",
            email="parent@example.test",
        )
        referenced_author.set_password("password")
        parent_author.set_password("password")
        db.session.add_all([referenced_author, parent_author])
        db.session.commit()

        referenced_recipe = Recipe(
            title="Tomatensaus",
            ingredients=["2 tomaten"],
            instructions=["Kook."],
            user_id=referenced_author.id,
            status=Recipe.STATUS_PUBLIC,
        )
        db.session.add(referenced_recipe)
        db.session.commit()

        parent_recipe = Recipe(
            title="Pasta",
            ingredients=[
                {
                    "type": "recipe",
                    "recipe_id": referenced_recipe.id,
                    "display_name": referenced_recipe.title,
                    "quantity": 1,
                    "unit": "portie",
                }
            ],
            instructions=["Meng."],
            user_id=parent_author.id,
            status=Recipe.STATUS_PUBLIC,
        )
        db.session.add(parent_recipe)
        db.session.commit()

        notifications = []
        monkeypatch.setattr(
            recipes_api,
            "send_referenced_recipe_update_notification",
            lambda dependent, recipe: notifications.append((dependent, recipe)),
        )

        update_recipe(
            recipe=referenced_recipe,
            title="Pittige tomatensaus",
            description=None,
            ingredients=["2 tomaten", "1 peper"],
            instructions=referenced_recipe.instructions,
            prep_time=None,
            cook_time=None,
            servings=2,
            category=None,
            status=Recipe.STATUS_PUBLIC,
        )

        assert notifications == [(parent_recipe, referenced_recipe)]


def test_recipe_form_rejects_empty_ingredient_and_instruction_lists(app):
    with app.test_request_context(
        "/",
        method="POST",
        data={
            "title": "Test recept",
            "ingredients-0": "   ",
            "instructions-0": "",
            "category": "",
            "status": "public",
        },
    ):
        form = RecipeForm()

        assert not form.validate()
        assert "Voeg minstens één ingrediënt toe." in form.ingredients.errors
        assert "Voeg minstens één instructiestap toe." in form.instructions.errors
