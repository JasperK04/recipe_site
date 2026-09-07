import re
import shutil
import sys
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path


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


def ingredient_to_string(ingredient: dict) -> str:
    if ingredient.get("type") == "recipe":
        parts = []
        if ingredient.get("quantity") is not None:
            parts.append(str(ingredient["quantity"]))
        if ingredient.get("unit"):
            parts.append(str(ingredient["unit"]))
        if ingredient.get("display_name"):
            parts.append(str(ingredient["display_name"]))
        return " ".join(parts)

    parts = []

    if ingredient.get("quantity") is not None:
        parts.append(str(ingredient["quantity"]))

    if ingredient.get("unit"):
        parts.append(ingredient["unit"])

    display_name = ingredient.get("display_name") or ingredient.get("name")
    if display_name:
        parts.append(display_name)

    return " ".join(parts)


def _normalize_ingredient_quantity(quantity):
    if quantity in (None, "") or not isinstance(quantity, str):
        return quantity
    try:
        number = float(quantity.strip().replace(",", "."))
    except ValueError:
        return quantity
    return int(number) if number.is_integer() else number


def sanitize_recipe_ingredients(
    raw_ingredients: list[str | dict] | None,
    plain_text: bool = False,
) -> list[dict] | list[str]:
    """Normalize all ingredient data to the canonical JSON representation."""
    ingredients = []
    for ingredient in raw_ingredients or []:
        if isinstance(ingredient, dict):
            if ingredient.get("type") == "recipe":
                from app.services.nested_recipes import validate_nested_recipe_reference

                normalized = validate_nested_recipe_reference(ingredient)
                if plain_text:
                    ingredients.append(__import__("json").dumps(normalized))
                else:
                    ingredients.append(normalized)
                continue

            name = (
                ingredient.get("display_name")
                or ingredient.get("name")
                or ingredient.get("name_")
            )
            if name:
                quantity = _normalize_ingredient_quantity(ingredient.get("quantity"))
                unit = ingredient.get("unit")
                normalized = {
                    "type": "ingredient",
                    "display_name": str(name).strip(),
                    "quantity": quantity,
                    "unit": str(unit or "").strip(),
                }
                if plain_text:
                    ingredients.append(__import__("json").dumps(normalized))
                else:
                    ingredients.append(normalized)
            continue

        if isinstance(ingredient, str):
            stripped = ingredient.strip()
            if not stripped:
                continue
            if stripped.startswith("{"):
                try:
                    parsed = __import__("json").loads(stripped)
                except __import__("json").JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    if parsed.get("type") == "recipe":
                        from app.services.nested_recipes import (
                            validate_nested_recipe_reference,
                        )

                        normalized = validate_nested_recipe_reference(parsed)
                        if plain_text:
                            ingredients.append(__import__("json").dumps(normalized))
                        else:
                            ingredients.append(normalized)
                    else:
                        name = (
                            parsed.get("display_name")
                            or parsed.get("name")
                            or parsed.get("name_")
                        )
                        if name:
                            quantity = _normalize_ingredient_quantity(
                                parsed.get("quantity")
                            )
                            unit = parsed.get("unit")
                            normalized = {
                                "type": "ingredient",
                                "display_name": str(name).strip(),
                                "quantity": quantity,
                                "unit": str(unit or "").strip(),
                            }
                            if plain_text:
                                ingredients.append(__import__("json").dumps(normalized))
                            else:
                                ingredients.append(normalized)
                    continue
            quantity, unit, name = parse_ingredient(ingredient)
            if name:
                if plain_text:
                    ingredients.append(
                        " ".join(
                            filter(
                                None,
                                [
                                    str(quantity) if quantity is not None else None,
                                    unit,
                                    name,
                                ],
                            )
                        )
                    )
                else:
                    ingredients.append(
                        {
                            "type": "ingredient",
                            "display_name": name,
                            "quantity": quantity,
                            "unit": unit or "",
                        }
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


def _parse_ingredient_value(value: str) -> float | int | None:
    """Parse a single numeric quantity value without raising for invalid input."""
    if value in {"½", "⅓", "¼", "¾"}:
        return {"½": 0.5, "⅓": 1 / 3, "¼": 0.25, "¾": 0.75}[value]
    if re.fullmatch(r"\d+/\d+", value):
        numerator, denominator = map(int, value.split("/"))
        return numerator / denominator if denominator else None
    if re.fullmatch(r"\d+(?:[.,]\d+)?", value):
        number = float(value.replace(",", "."))
        return int(number) if number.is_integer() else number
    return None


def parse_ingredient(text: str) -> tuple[float | int | None, str | None, str]:
    from utils.ingredient_normalization import is_configured_unit, normalize_unit

    text = text.lower().strip()

    # Recipe quantities are stored as a single number. Convert a range to its
    # nearest integer average (half values round up), without adding a new
    # field to the stored ingredient JSON.
    range_value = r"(?:\d+(?:[.,]\d+)?|\d+/\d+|[½⅓¼¾])"
    range_match = re.match(
        rf"^({range_value})\s*(?:-|–|—|tot|to|à)\s*({range_value})\s+(.+?)$",
        text,
    )
    if range_match:
        minimum = _parse_ingredient_value(range_match.group(1))
        maximum = _parse_ingredient_value(range_match.group(2))
        if minimum is not None and maximum is not None:
            average = int(((minimum + maximum) / 2) + 0.5)
            text = f"{average} {range_match.group(3)}"

    number_words = {
        "een": 1,
        "één": 1,
        "twee": 2,
        "drie": 3,
        "vier": 4,
        "vijf": 5,
        "zes": 6,
        "zeven": 7,
        "acht": 8,
        "negen": 9,
        "tien": 10,
        "elf": 11,
        "twaalf": 12,
    }

    fraction_chars = {
        "½": 0.5,
        "⅓": 1 / 3,
        "¼": 0.25,
        "¾": 0.75,
    }

    tokens = text.split()
    if not tokens:
        return None, None, ""

    amount = None
    consumed = 0

    first = tokens[0]
    attached_unit = None

    if first in fraction_chars:
        amount = fraction_chars[first]
        consumed = 1

    elif re.fullmatch(r"\d+/\d+", first):
        num, den = map(int, first.split("/"))
        if den == 0:
            return None, None, text
        amount = num / den
        consumed = 1

    elif re.fullmatch(r"\d+(?:[.,]\d+)?", first):
        amount = float(first.replace(",", "."))
        consumed = 1

    elif match := re.fullmatch(r"(\d+(?:[.,]\d+)?)([^\d\s]+)", first):
        amount = float(match.group(1).replace(",", "."))
        attached_unit = match.group(2)
        consumed = 1

    elif first in number_words:
        amount = number_words[first]
        consumed = 1

    if amount is None:
        # A configured unit at the start of an ingredient implies one unit:
        # "pond gehakt" is equivalent to "1 pond gehakt". Unknown leading
        # words remain ingredient names instead of being mistaken for units.
        if is_configured_unit(first) and len(tokens) >= 2:
            unit, multiplier = normalize_unit(first)
            amount = multiplier
            name = " ".join(tokens[1:])
            if isinstance(amount, float) and amount.is_integer():
                amount = int(amount)
            return amount, unit, name
        return None, None, text

    unit = None

    remaining = ([attached_unit] if attached_unit else []) + tokens[consumed:]

    # Support common mixed-fraction forms such as ``1 ½ kg`` and ``1 1/2 kg``.
    if remaining and remaining[0] in fraction_chars:
        amount += fraction_chars[remaining.pop(0)]
    elif remaining and re.fullmatch(r"\d+/\d+", remaining[0]):
        numerator, denominator = map(int, remaining[0].split("/"))
        if denominator:
            amount += numerator / denominator
            remaining.pop(0)

    if len(remaining) == 1:
        name = remaining[0]

    elif len(remaining) >= 2:
        first = remaining[0]

        unit, multiplier = normalize_unit(first)
        amount *= multiplier

        name = " ".join(remaining[1:])

    else:
        name = ""

    if isinstance(amount, float) and amount.is_integer():
        amount = int(amount)

    return amount, unit, name
