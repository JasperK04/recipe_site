import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from utils.upload import (
    normalize_category,
    normalize_instructions,
    parse_time,
    read_uploaded_page,
)


class UploadHelperTests(unittest.TestCase):
    sample_scrapes_dir = Path(__file__).parent / "sample_scrapes"
    def test_time_and_category_normalization(self):
        self.assertEqual(parse_time({"prepTime": "PT15M", "cookTime": "PT1H"}), (15, 60, 75))
        self.assertEqual(normalize_category(["hoofdgerecht"]), "Hoofdgerecht")
        self.assertEqual(normalize_category("unknown"), "Overig")

    def test_instruction_sections_are_flattened_without_section_names(self):
        instructions = [
            {
                "@type": "HowToSection",
                "name": "Voorbereiding",
                "itemListElement": [
                    {"@type": "HowToStep", "text": "Snijd de ui."},
                    {"@type": "HowToStep", "text": "Bak de ui."},
                ],
            }
        ]
        self.assertEqual(normalize_instructions(instructions), ["Snijd de ui.", "Bak de ui."])

    @patch("utils.upload.requests.get")
    def test_scraper_reads_recipe_json_ld(self, get):
        response = Mock()
        response.content = b'''<html><head><script type="application/ld+json">
        {"@graph": [{"@type": ["Thing", "Recipe"], "name": "Pasta", "description": "lekker",
        "recipeYield": "4", "prepTime": "PT10M", "cookTime": "PT20M",
        "recipeIngredient": ["200 g pasta"],
        "recipeInstructions": [{"@type": "HowToStep", "text": "Kook de pasta."}],
        "recipeCategory": "Hoofdgerecht"}]}
        </script></head></html>'''
        get.return_value = response

        self.assertEqual(
            read_uploaded_page("https://example.test/pasta"),
            {
                "name": "Pasta",
                "description": "Lekker",
                "servings": 4,
                "cook_time": 20,
                "prep_time": 10,
                "total_time": 30,
                "ingredients": ["200 g pasta"],
                "instructions": ["Kook de pasta."],
                "category": "Hoofdgerecht",
            },
        )
        get.assert_called_once_with(
            "https://example.test/pasta", headers={"User-Agent": "recipe retrieval system"}
        )
        response.raise_for_status.assert_called_once_with()

    @patch("utils.upload.read_page_with_llm", return_value={"name": "Fallback"})
    @patch("utils.upload.requests.get")
    def test_scraper_skips_invalid_json_ld_and_uses_fallback(self, get, read_page_with_llm):
        response = Mock()
        response.content = b'<script type="application/ld+json">not valid json</script>'
        get.return_value = response

        self.assertEqual(read_uploaded_page("https://example.test/broken"), {"name": "Fallback"})
        read_page_with_llm.assert_called_once()

    def test_saved_pages_match_their_gold_standard(self):
        class Response:
            def __init__(self, content):
                self.content = content

            def raise_for_status(self):
                pass

        for html_path in sorted(self.sample_scrapes_dir.glob("*.html")):
            with self.subTest(page=html_path.name):
                expected_path = html_path.with_suffix(".json")
                expected = json.loads(expected_path.read_text(encoding="utf-8"))
                with patch(
                    "utils.upload.requests.get",
                    return_value=Response(html_path.read_bytes()),
                ), patch("utils.upload.read_page_with_llm", return_value={}):
                    actual = read_uploaded_page("https://fixture.test/recipe")
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
