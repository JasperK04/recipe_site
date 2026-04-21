import io
from pathlib import Path
from uuid import uuid4

from flask import current_app
from PIL import Image, ImageOps
from utils import ensure_directory

MAX_IMAGE_WIDTH = 600
MAX_IMAGE_HEIGHT = 400


def _recipe_dir() -> Path:
    return ensure_directory(Path(current_app.config["RECIPE_IMAGE_DIR"]))


def _image_path(image_id: str) -> Path:
    return _recipe_dir() / f"{image_id}.webp"


def save_recipe_image(file_storage) -> str:
    """Save uploaded image as resized WebP in DATAROOT/recipe and return image id."""
    file_storage.stream.seek(0)
    img = Image.open(file_storage.stream)
    img = ImageOps.exif_transpose(img)
    img.thumbnail((MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT), Image.Resampling.LANCZOS)

    converted = img.convert("RGBA" if img.mode in ("RGBA", "LA") else "RGB")
    output = io.BytesIO()
    converted.save(output, format="WEBP")

    image_id = uuid4().hex
    _image_path(image_id).write_bytes(output.getvalue())
    return image_id


def read_recipe_image_bytes(image_id: str | None) -> bytes | None:
    if not image_id:
        return None
    path = _image_path(image_id)
    if not path.is_file():
        return None
    return path.read_bytes()


def delete_recipe_image(image_id: str | None) -> None:
    if not image_id:
        return
    path = _image_path(image_id)
    if path.is_file():
        path.unlink()
