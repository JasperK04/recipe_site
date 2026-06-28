"""Shared API helpers and API blueprint entry point."""

from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

from app.api.common import ApiError  # noqa: E402
from app.api.recipes import (  # noqa: E402
    create_recipe,
    deactivate_recipe,
    delete_recipe,
    reactivate_recipe,
    record_recipe_score,
    toggle_recipe_favorite,
    update_recipe,
)
from app.api.users import (  # noqa: E402
    cleanup_expired_otc_codes,
    create_registration_otc,
    deactivate_user,
    demote_user,
    promote_user,
    reactivate_user,
    register_user,
    submit_creator_request,
    update_profile,
)

__all__ = [
    "api_bp",
    "ApiError",
    "create_recipe",
    "deactivate_recipe",
    "delete_recipe",
    "reactivate_recipe",
    "record_recipe_score",
    "toggle_recipe_favorite",
    "update_recipe",
    "register_user",
    "update_profile",
    "submit_creator_request",
    "cleanup_expired_otc_codes",
    "create_registration_otc",
    "deactivate_user",
    "reactivate_user",
    "promote_user",
    "demote_user",
]
