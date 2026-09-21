from __future__ import annotations

from pathlib import Path

from flask import current_app

PENDING_RECIPE_IMAGE_TOKEN_SESSION_KEY = "pending_recipe_image_token"


def pending_recipe_image_path(token: str) -> Path:
    return Path(current_app.config["DATA_ROOT"]) / "recipe_import" / f"{token}.img"


def delete_pending_recipe_image(token: str | None) -> None:
    if token:
        pending_recipe_image_path(token).unlink(missing_ok=True)
