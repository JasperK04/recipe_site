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
    parts = []

    if ingredient.get("quantity") is not None:
        parts.append(str(ingredient["quantity"]))

    if ingredient.get("measurement"):
        parts.append(ingredient["measurement"])

    if ingredient.get("name"):
        parts.append(ingredient["name"])

    return " ".join(parts)


def sanitize_recipe_ingredients(
    raw_ingredients: list[str] | None,
    plain_text: bool = False,
) -> list[dict] | list[str]:
    """Normalize ingredient data from recipe forms."""
    ingredients = []
    for ingredient in raw_ingredients or []:
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
                    {"name": name, "quantity": quantity, "measurement": unit}
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


def parse_ingredient(text: str) -> tuple[float | int | None, str | None, str]:
    text = text.lower().strip()

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

    unit_multipliers = {
        "ons": ("g", 100),
        "pond": ("g", 500),
        "dozijn": ("st", 12),
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

    if first in fraction_chars:
        amount = fraction_chars[first]
        consumed = 1

    elif re.fullmatch(r"\d+/\d+", first):
        num, den = map(int, first.split("/"))
        amount = num / den
        consumed = 1

    elif re.fullmatch(r"\d+(?:[.,]\d+)?", first):
        amount = float(first.replace(",", "."))
        consumed = 1

    elif first in number_words:
        amount = number_words[first]
        consumed = 1

    if amount is None:
        return None, None, text

    unit = None

    remaining = tokens[consumed:]

    if len(remaining) == 1:
        name = remaining[0]

    elif len(remaining) >= 2:
        first = remaining[0]

        if first in unit_multipliers:
            unit, multiplier = unit_multipliers[first]
            amount *= multiplier
        else:
            unit = first

        name = " ".join(remaining[1:])

    else:
        name = ""

    if isinstance(amount, float) and amount.is_integer():
        amount = int(amount)

    return amount, unit, name
