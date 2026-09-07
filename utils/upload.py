import io
import ipaddress
import json
import re
import socket
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import requests
from bs4 import BeautifulSoup
from flask import flash
from PIL import Image

MAX_IMPORTED_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_DOWNLOAD_TIMEOUT = (5, 15)


def sanitize_text(text: str) -> str:
    """Sanitize text by removing extra whitespace and unwanted characters."""
    text = unescape(text)
    text = re.sub(r"\<p\>", "", text)
    text = re.sub(r"\<\/p\>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\\*", "", text)
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


def parse_time(recipe: dict) -> tuple[int | None, int | None, int | None]:

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


def normalize_ingredient(ing: list | None) -> list[str]:
    if not ing:
        return [""]
    ingredients = []
    for item in ing:
        if isinstance(item, str):
            ingredients.append(sanitize_text(item.strip()))
    return ingredients


def normalize_instructions(raw_steps: list | None) -> list[str]:
    """Normalize instruction steps from recipe forms."""

    def flatten_recipe_instructions(recipe_instructions):
        steps = []

        def walk(node):
            if isinstance(node, str):
                steps.append(node)

            elif isinstance(node, dict):
                node_types = node.get("@type", [])
                if isinstance(node_types, str):
                    node_types = [node_types]

                if "HowToStep" in node_types:
                    text = node.get("text")
                    if text:
                        steps.append(text)
                    return

                # Sections are containers, not instructions.  Traversing every
                # value would also add their ``@type`` and ``name`` fields.
                if "HowToSection" in node_types:
                    walk(node.get("itemListElement", []))
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
    from openai import OpenAI

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
    "ingredients": [string, ...],
    "instructions": [string, ...],
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


def _image_url(value: object, page_url: str) -> str | None:
    if isinstance(value, str):
        candidate = value.strip()
    elif isinstance(value, dict):
        candidate = str(value.get("url") or value.get("contentUrl") or "").strip()
    else:
        return None
    if not candidate:
        return None
    absolute = urljoin(page_url, candidate)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return absolute


def extract_recipe_image_url(
    recipe: dict, soup: BeautifulSoup, page_url: str
) -> str | None:
    image = recipe.get("image")
    candidates = image if isinstance(image, list) else [image]
    for candidate in candidates:
        image_url = _image_url(candidate, page_url)
        if image_url:
            return image_url

    og_image = soup.find("meta", attrs={"property": "og:image"})
    return _image_url(og_image.get("content") if og_image else None, page_url)


def _public_hostname(hostname: str) -> bool:
    try:
        addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    return all(ipaddress.ip_address(address[4][0]).is_global for address in addresses)


def download_recipe_image(url: str, target_dir: Path) -> str | None:
    """Download one validated external image and return its temporary token."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if not _public_hostname(parsed.hostname):
        return None

    response = None
    try:
        for _ in range(3):
            response = requests.get(
                url,
                headers={"User-Agent": "recipe image retrieval system"},
                stream=True,
                timeout=IMAGE_DOWNLOAD_TIMEOUT,
                allow_redirects=False,
            )
            if response.is_redirect:
                url = urljoin(url, response.headers.get("Location", ""))
                parsed = urlparse(url)
                if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.hostname
                    or not _public_hostname(parsed.hostname)
                ):
                    return None
                continue
            break
        else:
            return None

        if response.status_code != 200:
            return None
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if content_type and not content_type.startswith("image/"):
            return None
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_IMPORTED_IMAGE_BYTES:
            return None

        content = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            content.extend(chunk)
            if len(content) > MAX_IMPORTED_IMAGE_BYTES:
                return None
        with Image.open(io.BytesIO(content)) as image:
            image.verify()

        target_dir.mkdir(parents=True, exist_ok=True)
        token = uuid4().hex
        (target_dir / f"{token}.img").write_bytes(content)
        return token
    except (OSError, ValueError, TypeError, requests.RequestException):
        return None
    finally:
        if response is not None:
            response.close()


def read_uploaded_page(url: str, *, include_image: bool = False) -> dict:
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
    recipe: dict | None = None
    for script in raw_scripts:
        if not script or not script.string:
            continue

        try:
            raw_data = json.loads(script.string, strict=False)
        except json.JSONDecodeError:
            continue
        if isinstance(raw_data, dict):
            raw_graph = raw_data.get("@graph") or [raw_data]
        elif isinstance(raw_data, list):
            raw_graph = raw_data
        else:
            continue
        for item in raw_graph:
            item_types = item.get("@type", []) if isinstance(item, dict) else []
            if isinstance(item_types, str):
                item_types = [item_types]
            if isinstance(item, dict) and "Recipe" in item_types:
                recipe = item
                found_recipe = True
                break
        if found_recipe:
            break

    else:
        print("No Recipe type found in JSON-LD, falling back to LLM parsing.")
        formatted_data = read_page_with_llm(soup)
        if include_image:
            image_url = extract_recipe_image_url({}, soup, url)
            if image_url:
                formatted_data["image_url"] = image_url
        return formatted_data
    if recipe is None:
        formatted_data = read_page_with_llm(soup)
        if include_image:
            image_url = extract_recipe_image_url({}, soup, url)
            if image_url:
                formatted_data["image_url"] = image_url
        return formatted_data
    # print(recipe)
    prep_time, cook_time, total_time = parse_time(recipe)
    formatted_data = {
        "name": sanitize_text(recipe.get("name", "").strip()),
        "description": sanitize_text(recipe.get("description", "")),
        "servings": normalize_servings(recipe.get("recipeYield")),
        "cook_time": cook_time,
        "prep_time": prep_time,
        "total_time": total_time,
        "ingredients": normalize_ingredient(recipe.get("recipeIngredient", [])),
        "instructions": normalize_instructions(recipe.get("recipeInstructions", [])),
        "category": normalize_category(recipe.get("recipeCategory")),
    }
    if include_image:
        image_url = extract_recipe_image_url(recipe, soup, url)
        if image_url:
            formatted_data["image_url"] = image_url
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
