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

    def test_count_units_are_removed_from_the_unit(self):
        self.assertEqual(parse_ingredient("2 st eieren"), (2, None, "eieren"))
        self.assertEqual(parse_ingredient("1 dozijn eieren"), (12, None, "eieren"))

    def test_only_configured_words_are_consumed_as_units(self):
        self.assertEqual(parse_ingredient("1 rode ui"), (1, None, "rode ui"))
        self.assertEqual(
            parse_ingredient("2 teentjes knoflook"), (2, "teentjes", "knoflook")
        )

    def test_aliases_conversions_and_self_units_use_the_config(self):
        self.assertEqual(parse_ingredient("1 gram bloem"), (1, "g", "bloem"))
        self.assertEqual(parse_ingredient("1 ons bloem"), (100, "g", "bloem"))
        self.assertEqual(
            parse_ingredient("1 teentje knoflook"), (1, "teentje", "knoflook")
        )

    def test_common_dutch_self_units_are_preserved(self):
        cases = {
            "een snufje zout": (1, "snufje", "zout"),
            "2 scheutjes olie": (2, "scheutjes", "olie"),
            "een handje peterselie": (1, "handje", "peterselie"),
            "3 takjes tijm": (3, "takjes", "tijm"),
            "2 plakjes kaas": (2, "plakjes", "kaas"),
            "1 mespuntje peper": (1, "mespuntje", "peper"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_ingredient(text), expected)

    def test_implicit_and_absent_units(self):
        self.assertEqual(parse_ingredient("kg bloem"), (1, "kg", "bloem"))
        self.assertEqual(parse_ingredient("st eieren"), (1, None, "eieren"))
        self.assertEqual(parse_ingredient("dozijn eieren"), (12, None, "eieren"))
        self.assertEqual(parse_ingredient("2 eieren"), (2, None, "eieren"))
        self.assertEqual(parse_ingredient("eieren"), (None, None, "eieren"))

    def test_unknown_words_are_kept_in_the_ingredient_name(self):
        self.assertEqual(parse_ingredient("2 schep zout"), (2, None, "schep zout"))
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
                {
                    "type": "ingredient",
                    "display_name": "eieren",
                    "quantity": 3,
                    "unit": "",
                },
                {
                    "type": "ingredient",
                    "display_name": "bloem",
                    "quantity": 3,
                    "unit": "kg",
                },
            ],
        )
        self.assertEqual(ingredient_to_string(ingredients[0]), "3 eieren")  # type: ignore

    def test_backfill_is_idempotent(self):
        once = normalize_stored_ingredients(
            [
                {
                    "name": "kaas",
                    "quantity": 2,
                    "unit": "ons",
                }
            ]
        )
        self.assertEqual(
            once,
            [
                {
                    "type": "ingredient",
                    "display_name": "kaas",
                    "quantity": 200,
                    "unit": "g",
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
                {
                    "type": "ingredient",
                    "display_name": "bloem",
                    "quantity": 2,
                    "unit": "kg",
                },
                {
                    "type": "ingredient",
                    "display_name": "olie",
                    "quantity": 3,
                    "unit": "el",
                },
            ],
        )

    def test_stored_ingredients_can_be_reapplied(self):
        self.assertEqual(
            normalize_stored_ingredients(
                [
                    {"name": "bloem", "quantity": 2, "unit": "kilo"},
                    {"name_": "olie", "quantity": 3, "unit": "eetlepel"},
                ]
            ),
            [
                {
                    "type": "ingredient",
                    "display_name": "bloem",
                    "quantity": 2,
                    "unit": "kg",
                },
                {
                    "type": "ingredient",
                    "display_name": "olie",
                    "quantity": 3,
                    "unit": "el",
                },
            ],
        )

    def test_backfill_reparses_previously_misclassified_units(self):
        self.assertEqual(
            normalize_stored_ingredients(
                [{"display_name": "ui", "quantity": 1, "unit": "rode"}]
            ),
            [
                {
                    "type": "ingredient",
                    "display_name": "rode ui",
                    "quantity": 1,
                    "unit": "",
                }
            ],
        )

    def test_nested_recipe_ingredients_render_as_human_readable_strings(self):
        nested = {
            "type": "recipe",
            "recipe_id": 42,
            "display_name": "Tomatensaus",
            "quantity": 1,
            "unit": "portie",
        }

        self.assertEqual(
            ingredient_to_string(nested),
            "1 portie Tomatensaus",
        )
        self.assertEqual(
            sanitize_recipe_ingredients([nested], plain_text=True),
            [
                '{"type": "recipe", "recipe_id": 42, "display_name": "Tomatensaus", "quantity": 1, "unit": "portie"}'
            ],
        )


if __name__ == "__main__":
    unittest.main()
