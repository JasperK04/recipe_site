import json
import os
import tempfile
import unittest

from utils.general import (
    ingredient_to_string,
    parse_ingredient,
    sanitize_recipe_ingredients,
)
from utils.ingredient_normalization import (
    normalize_stored_ingredients,
    normalize_unit,
    reload_unit_normalization,
)


class IngredientNormalizationTests(unittest.TestCase):
    def test_configured_aliases_and_multipliers_are_applied(self):
        self.assertEqual(parse_ingredient("2 kg bloem"), (2, "kg", "bloem"))
        self.assertEqual(parse_ingredient("2 ons kaas"), (200, "g", "kaas"))
        self.assertEqual(parse_ingredient("pond gehakt"), (500, "g", "gehakt"))
        self.assertEqual(parse_ingredient("3 eetlepels olie"), (3, "el", "olie"))

    def test_count_units_are_removed_from_the_measurement(self):
        self.assertEqual(parse_ingredient("2 st eieren"), (2, None, "eieren"))
        self.assertEqual(parse_ingredient("1 dozijn eieren"), (12, None, "eieren"))

    def test_implicit_and_absent_units(self):
        self.assertEqual(parse_ingredient("kg bloem"), (1, "kg", "bloem"))
        self.assertEqual(parse_ingredient("st eieren"), (1, None, "eieren"))
        self.assertEqual(parse_ingredient("dozijn eieren"), (12, None, "eieren"))
        self.assertEqual(parse_ingredient("2 eieren"), (2, None, "eieren"))
        self.assertEqual(parse_ingredient("eieren"), (None, None, "eieren"))

    def test_unknown_units_are_kept_as_units(self):
        self.assertEqual(parse_ingredient("2 snuf zout"), (2, "snuf", "zout"))
        self.assertEqual(normalize_unit("SnUf"), ("snuf", 1))

    def test_existing_number_and_fraction_parsing_is_preserved(self):
        self.assertEqual(parse_ingredient("½ tl kaneel"), (0.5, "tl", "kaneel"))
        self.assertEqual(
            parse_ingredient("twee pond aardappels"), (1000, "g", "aardappels")
        )
        self.assertEqual(parse_ingredient("bloem"), (None, None, "bloem"))

    def test_decimal_and_mixed_fraction_parsing(self):
        self.assertEqual(parse_ingredient("1,5 kg bloem"), (1.5, "kg", "bloem"))
        self.assertEqual(parse_ingredient("1.5 kg bloem"), (1.5, "kg", "bloem"))
        self.assertEqual(parse_ingredient("1/2 kg bloem"), (0.5, "kg", "bloem"))
        self.assertEqual(parse_ingredient("1 ½ kg bloem"), (1.5, "kg", "bloem"))
        self.assertEqual(parse_ingredient("1 1/2 kg bloem"), (1.5, "kg", "bloem"))

    def test_compact_and_punctuated_units(self):
        self.assertEqual(parse_ingredient("200g bloem"), (200, "g", "bloem"))
        self.assertEqual(parse_ingredient("2 KG bloem"), (2, "kg", "bloem"))
        self.assertEqual(parse_ingredient("2 kg. bloem"), (2, "kg", "bloem"))

    def test_invalid_fraction_does_not_raise(self):
        self.assertEqual(parse_ingredient("1/0 kg bloem"), (None, None, "1/0 kg bloem"))

    def test_quantity_ranges_are_averaged_to_a_whole_number(self):
        cases = {
            "2-3 eieren": (3, None, "eieren"),
            "2–3 eieren": (3, None, "eieren"),
            "2 tot 3 kg bloem": (3, "kg", "bloem"),
            "2 to 3 eieren": (3, None, "eieren"),
            "2 à 3 eieren": (3, None, "eieren"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_ingredient(text), expected)

    def test_ranges_are_averaged_when_sanitized_and_displayed(self):
        ingredients = sanitize_recipe_ingredients(["2-3 eieren", "2 tot 3 kg bloem"])
        self.assertEqual(
            ingredients,
            [
                {"name": "eieren", "quantity": 3, "measurement": None},
                {"name": "bloem", "quantity": 3, "measurement": "kg"},
            ],
        )
        self.assertEqual(ingredient_to_string(ingredients[0]), "3 eieren")  # type: ignore

    def test_backfill_is_idempotent(self):
        once = normalize_stored_ingredients(
            [
                {
                    "name": "kaas",
                    "quantity": 2,
                    "measurement": "ons",
                }
            ]
        )
        self.assertEqual(
            once,
            [
                {
                    "name": "kaas",
                    "quantity": 200,
                    "measurement": "g",
                }
            ],
        )
        self.assertEqual(normalize_stored_ingredients(once), once)

    def test_invalid_configuration_is_rejected(self):
        invalid_configs = [
            "{",
            json.dumps({"units": {"kg": {"unit": "g", "multiplier": "many"}}}),
            json.dumps({"units": {"kg": {"unit": 4}}}),
        ]
        original_path = os.environ.get("INGREDIENT_NORMALIZATION_FILE")
        try:
            for config in invalid_configs:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False
                ) as file:
                    file.write(config)
                    config_path = file.name
                try:
                    os.environ["INGREDIENT_NORMALIZATION_FILE"] = config_path
                    reload_unit_normalization()
                    with self.assertRaises(
                        (TypeError, ValueError, json.JSONDecodeError)
                    ):
                        normalize_unit("kg")
                finally:
                    os.unlink(config_path)
        finally:
            if original_path is None:
                os.environ.pop("INGREDIENT_NORMALIZATION_FILE", None)
            else:
                os.environ["INGREDIENT_NORMALIZATION_FILE"] = original_path
            reload_unit_normalization()

    def test_recipe_form_ingredients_use_the_same_rules(self):
        self.assertEqual(
            sanitize_recipe_ingredients(["2 kg bloem", "3 eetlepels olie"]),
            [
                {"name": "bloem", "quantity": 2, "measurement": "kg"},
                {"name": "olie", "quantity": 3, "measurement": "el"},
            ],
        )

    def test_stored_ingredients_can_be_reapplied(self):
        self.assertEqual(
            normalize_stored_ingredients(
                [
                    {"name": "bloem", "quantity": 2, "measurement": "kg"},
                    {"name_": "olie", "quantity": 3, "measurement": "eetlepel"},
                ]
            ),
            [
                {"name": "bloem", "quantity": 2, "measurement": "kg"},
                {"name": "olie", "quantity": 3, "measurement": "el"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
