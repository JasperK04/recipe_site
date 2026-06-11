import json
import re
from collections.abc import Iterable

import requests
from bs4 import BeautifulSoup
from flask import flash
from openai import OpenAI


def sanitize_text(text: str) -> str:
    """Sanitize text by removing extra whitespace and newlines."""
    text = re.sub(r"\<p\>", "", text)
    text = re.sub(r"\<\/p\>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.capitalize()


def normalize_servings(value: list[str] | str | None) -> int | None:
    if not value:
        return None
    if isinstance(value, list):
        value = value[0]
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_time(recipe: dict) -> tuple[int | None, int | None, int | None]:

    def extract_minutes(value: str | None) -> int | None:
        hours = re.findall(r"(\d+)h", value or "", re.IGNORECASE)
        minutes = re.findall(r"(\d+)m", value or "", re.IGNORECASE)
        total_minutes = 0
        for h in hours:
            total_minutes += int(h) * 60
        for m in minutes:
            total_minutes += int(m)
        if not value:
            return None
        try:
            return total_minutes if total_minutes > 0 else None
        except (TypeError, ValueError):
            print(f"Could not parse time value: {value}")
            return None

    prep_time = extract_minutes(recipe.get("prepTime"))
    cook_time = extract_minutes(recipe.get("cookTime"))
    total_time = extract_minutes(recipe.get("totalTime"))

    if (
        total_time is None and prep_time is not None and cook_time is not None
    ):  # no total time
        total_time = prep_time + cook_time
    elif (
        total_time is not None and cook_time is not None and prep_time is None
    ):  # no prep time
        prep_time = total_time - cook_time
    elif (
        total_time is not None and prep_time is not None and cook_time is None
    ):  # no cook time
        cook_time = total_time - prep_time

    elif (
        total_time is not None and prep_time is None and cook_time is None
    ):  # only total time
        prep_time = total_time
    elif (
        total_time is None and prep_time is not None and cook_time is None
    ):  # only prep time
        total_time = prep_time
    elif (
        total_time is None and prep_time is None and cook_time is not None
    ):  # only cook time
        total_time = cook_time

    return prep_time, cook_time, total_time


def normalize_category(value: list[str] | str | None) -> str | None:
    allowed = {
        "ontbijt": "Ontbijt",
        "lunch": "Lunch",
        "voorgerecht": "Voorgerecht",
        "hoofdgerecht": "Hoofdgerecht",
        "nagerecht": "Nagerecht",
        "drank": "Drank",
        "snack": "Snack",
        "overig": "Overig",
    }
    if not value:
        return None
    if isinstance(value, list):
        value = value[0]
    normalized = str(value).strip().lower()
    return allowed.get(normalized, "Overig")


def normalize_ingredients(raw_ingredients: Iterable[str] | None) -> list[dict]:
    """Normalize ingredient data from recipe forms."""

    def get_quantity(ing: str) -> str | None:
        matches = re.findall(r"(\d+)", ing[:5])
        return matches[0] if matches else None

    def get_measurement(ing: str, has_quantity: bool) -> tuple[str | None, str | None]:
        mapped_units = {
            "gr": "g",
            "eetlepel": "el",
            "theelepel": "tl",
        }
        units = ["gr", "g", "kg", "ml", "l", "el", "tl", "eetlepel", "theelepel"]
        for unit in units:
            if re.search(rf"\b{unit}\b", ing, re.IGNORECASE):
                return mapped_units.get(unit, unit), unit
        if has_quantity:
            return "stuks", "stuks"
        return None, None

    def get_name(ing: str, quantity: str | None, measurement: str | None) -> str:
        ing = re.sub(rf"\b{quantity or ''}", "", ing)
        ing = re.sub(rf"{measurement or ''}\b", "", ing)
        return ing.strip()

    ingredients = []

    for ing in raw_ingredients or []:
        ing = sanitize_text(ing)
        quantity = get_quantity(ing)
        measurement, original_unit = get_measurement(ing, bool(quantity))
        name_ = get_name(ing, quantity, original_unit)
        ingredients.append(
            {
                "name_": name_,
                "quantity": quantity,
                "measurement": measurement,
            }
        )
    return ingredients


def normalize_instructions(raw_steps: list | None) -> list[str]:
    """Normalize instruction steps from recipe forms."""

    def flatten_recipe_instructions(recipe_instructions):
        steps = []

        def walk(node):
            if isinstance(node, str):
                steps.append(node)

            elif isinstance(node, dict):
                if node.get("@type") == "HowToStep":
                    text = node.get("text")
                    if text:
                        steps.append(text)
                    return

                for value in node.values():
                    walk(value)

            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(recipe_instructions)
        return steps

    return [
        str(sanitize_text(step)).strip()
        for step in flatten_recipe_instructions(raw_steps or [])
        if str(sanitize_text(step)).strip()
    ]


def parse_uploaded_text(text: str) -> dict:
    """Parse a text file with recipe data in a simple custom format."""
    system_prompt = """
The text contains information about a recipe like Name, Description, Servings, Prep Time, Ingredients, and Instructions. 
Extract the relevant information and return it as a JSON object with the following structure:
{
    "name": string,
    "description": string | null,
    "servings": numerical string | null,
    "prep_time": numerical string (minutes) | null,
    "cook_time": numerical string (minutes) | null,
    "total_time": numerical string (minutes) | null,
    "ingredients": [{
        "name_": string, 
        "quantity": numerical string, 
        "measurement": literal string (e.g. "g", "kg", "ml", "l", "el", "tl", "stuks")
    }],
    "instructions": [string],
    "category": literal string (e.g. "Ontbijt", "Lunch", "Voorgerecht", "Hoofdgerecht", "Nagerecht", "Drank", "Snack" or "Overig") | null,
}
"""
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-5.4-nano",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": "parse the following text into a JSON object:\n\n" + text,
            },
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        print("LLM did not return any content.")
        return {}
    return validate_uploaded_json(
        json.loads(content),
        required_keys=["name", "ingredients", "instructions"],
    )


def read_page_with_llm(soup: BeautifulSoup) -> dict:
    # Implementation for reading page with LLM
    page_text = soup.get_text(separator="\n", strip=True)
    return parse_uploaded_text(page_text)


def read_uploaded_page(url: str) -> dict:
    """Read and parse a web page for recipe data."""
    # Implementation for reading uploaded page
    headers = {
        "User-Agent": "recipe retrieval system",
    }
    page = requests.get(url, headers=headers)
    page.raise_for_status()
    soup = BeautifulSoup(page.content, "html.parser")
    raw_scripts = soup.find_all("script", {"type": "application/ld+json"})
    found_recipe = False
    for script in raw_scripts:
        if not script or not script.string:
            continue

        raw_data = json.loads(script.string, strict=False)
        raw_graph = raw_data.get("@graph") or [raw_data]
        for item in raw_graph:
            if isinstance(item, dict) and item.get("@type") == "Recipe":
                recipe = item
                found_recipe = True
                break
        if found_recipe:
            break

    else:
        print("No Recipe type found in JSON-LD, falling back to LLM parsing.")
        return read_page_with_llm(soup)
    # print(recipe)
    prep_time, cook_time, total_time = normalize_time(recipe)
    formatted_data = {
        "name": sanitize_text(recipe.get("name", "").strip()),
        "description": sanitize_text(recipe.get("description", "")),
        "servings": normalize_servings(recipe.get("recipeYield")),
        "cook_time": cook_time,
        "prep_time": prep_time,
        "total_time": total_time,
        "ingredients": normalize_ingredients(recipe.get("recipeIngredient", [])),
        "instructions": normalize_instructions(recipe.get("recipeInstructions", [])),
        "category": normalize_category(recipe.get("recipeCategory")),
    }
    return validate_uploaded_json(
        formatted_data, required_keys=["name", "ingredients", "instructions"]
    )


def validate_uploaded_json(json_: dict, required_keys: list[str]) -> dict:
    """Validate and parse an uploaded JSON file for recipe data."""
    # Implementation for validating uploaded file
    missing_keys = [key for key in required_keys if key not in json_]
    if missing_keys:
        print(f"Uploaded JSON is missing required keys: {', '.join(missing_keys)}")
        flash(
            f"Uploaded JSON is missing required keys: {', '.join(missing_keys)}",
            "danger",
        )
        return {}
    return json_
