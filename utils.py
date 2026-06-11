import json
import re
import shutil
import sys
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from flask import flash
from openai import OpenAI


def ensure_directory(path: str | Path) -> Path:
    """Ensure directory exists and return it as a Path."""
    directory = Path(path).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def resolve_data_root(raw_path: str | None, *, base_dir: str | Path) -> Path:
    """Resolve DATAROOT to an absolute directory path."""
    value = (raw_path or "data").strip()
    root = Path(value).expanduser()
    if not root.is_absolute():
        root = Path(base_dir) / root
    return ensure_directory(root.resolve())


def normalize_sqlite_uri(uri: str | None, *, base_dir: str | Path) -> str | None:
    """Normalize file-based SQLite URIs to absolute paths."""
    if not uri:
        return uri

    uri = str(uri)
    if not uri.startswith("sqlite:") or uri.endswith(":memory:"):
        return uri

    if uri.startswith("sqlite:////"):
        return uri

    if uri.startswith("sqlite:///"):
        rel_path = uri[len("sqlite:///") :]
        abs_path = (Path(base_dir) / rel_path).resolve()
        ensure_directory(abs_path.parent)
        return f"sqlite:///{abs_path.as_posix()}"

    return uri


def sqlite_path_from_uri(uri: str | None) -> str | None:
    """Convert sqlite:/// URI to a filesystem path, or None for non-sqlite URIs."""
    if not uri:
        return None
    if uri.startswith("sqlite:////"):
        return "/" + uri[len("sqlite:////") :]
    if uri.startswith("sqlite:///"):
        return uri[len("sqlite:///") :]
    return None


def is_running_flask_db_command(argv: Sequence[str] | None = None) -> bool:
    """Return True when command line appears to be a Flask db command."""
    args = [arg.lower() for arg in (argv or sys.argv[1:4])]
    return "db" in args


def clear_directory_files(directory: str | Path, *, pattern: str = "*") -> int:
    """Delete matching files in a directory and return number of deleted files."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return 0

    deleted = 0
    for path in dir_path.glob(pattern):
        if path.is_file():
            try:
                path.unlink()
                deleted += 1
            except OSError:
                continue
    return deleted


def create_zip_from_directory(
    source_dir: str | Path,
    zip_path: str | Path,
    *,
    archive_root: str,
    pattern: str = "*",
) -> int:
    """Create/overwrite zip file from files in source_dir; return file count."""
    src_dir = ensure_directory(source_dir)
    out_zip = Path(zip_path)
    ensure_directory(out_zip.parent)
    if out_zip.exists():
        out_zip.unlink()

    root = archive_root.rstrip("/")
    file_count = 0
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{root}/", "")
        for file_path in sorted(src_dir.glob(pattern)):
            if file_path.is_file():
                archive.write(file_path, arcname=f"{root}/{file_path.name}")
                file_count += 1
    return file_count


def restore_directory_from_zip(
    zip_path: str | Path,
    target_dir: str | Path,
    *,
    pattern: str = "*",
) -> int:
    """Replace target directory with zip contents and return number of files restored."""
    archive_path = Path(zip_path)
    if not archive_path.is_file():
        raise FileNotFoundError(str(archive_path))

    target = Path(target_dir)
    parent = ensure_directory(target.parent)
    if target.exists():
        shutil.rmtree(target)

    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(parent)

    ensure_directory(target)
    return count_files(target, pattern=pattern)


def count_files(directory: str | Path, *, pattern: str = "*") -> int:
    """Count files in directory matching a glob pattern."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return 0
    return sum(1 for path in dir_path.glob(pattern) if path.is_file())


def sanitize_recipe_ingredients(raw_ingredients: Iterable[dict] | None) -> list[dict]:
    """Normalize ingredient data from recipe forms."""
    ingredients = []
    for ing in raw_ingredients or []:
        ing = ing or {}
        name = str(ing.get("name_") or "").strip()
        qty_raw = str(ing.get("quantity") or "").strip()
        measurement = str(ing.get("measurement") or "").strip()
        if not name and not qty_raw and not measurement:
            continue

        quantity: float | str | None = None
        if qty_raw:
            try:
                quantity = float(qty_raw)
            except (TypeError, ValueError):
                quantity = qty_raw

        ingredients.append(
            {"name_": name, "quantity": quantity, "measurement": measurement}
        )
    return ingredients


def sanitize_recipe_instructions(raw_steps: Iterable[str] | None) -> list[str]:
    """Normalize instruction steps from recipe forms."""
    instructions = []
    for step in raw_steps or []:
        text = str(step or "").strip()
        if text:
            instructions.append(text)
    return instructions


def normalize_choice(
    value: str | None,
    *,
    allowed: Iterable[str],
    default: str,
) -> str:
    """Normalize string input and ensure it is one of the allowed values."""
    normalized = str(value or "").strip().lower()
    allowed_set = set(allowed)
    return normalized if normalized in allowed_set else default


def to_model_choices(
    items: Iterable[object], *, id_attr: str = "id", label_attr: str = "name"
) -> list[tuple]:
    """Convert model objects to (id, label) tuples for WTForms choices."""
    return [(getattr(item, id_attr), getattr(item, label_attr)) for item in items]


def query_rows_by_ids(model, row_ids: Iterable[int] | None) -> list:
    """Load rows by primary-key ids from a SQLAlchemy model."""
    ids = [row_id for row_id in (row_ids or []) if row_id is not None]
    if not ids:
        return []
    return model.query.filter(model.id.in_(ids)).all()


def require_active_admin(user) -> None:
    """Abort with 401/403 unless user is an active admin."""
    from flask import abort

    if not getattr(user, "is_authenticated", False):
        abort(401)
    if not getattr(user, "is_active", False) or not getattr(user, "is_admin", False):
        abort(403)


def require_active_creator(user) -> None:
    """Abort with 401/403 unless user can create recipes."""
    from flask import abort

    if not getattr(user, "is_authenticated", False):
        abort(401)
    if not getattr(user, "can_create_recipes", False):
        abort(403)


def normalize_servings(value: list | str | None) -> int | None:
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
        matches = re.findall(r"(\d+)", ing)
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
        ing = re.sub(rf"{quantity or ''}", "", ing)
        ing = re.sub(rf"{measurement or ''}", "", ing)
        return ing.strip()

    ingredients = []

    for ing in raw_ingredients or []:
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
            if isinstance(node, dict):
                if node.get("@type") == "HowToStep":
                    steps.append(node)
                    return

                for value in node.values():
                    walk(value)

            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(recipe_instructions)
        return steps

    instructions = []
    for step in flatten_recipe_instructions(raw_steps or []):
        text = str(step.get("text") or "").strip()
        if text:
            instructions.append(text)
    return instructions


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
                "content": "parse the following text:\n\n" + text,
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
        "name": recipe.get("name", "").strip(),
        "description": recipe.get("description", ""),
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
