"""Shared API helpers and API blueprint entry point."""

from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

from app.api.common import ApiError
from app.api.recipes import (
    allow_recipe_moderation,
    create_recipe,
    deactivate_recipe,
    delete_recipe,
    pending_recipe_moderation_count,
    reactivate_recipe,
    record_recipe_score,
    retest_all_recipe_moderation,
    toggle_recipe_favorite,
    update_recipe,
)
from app.api.users import (
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
    "ApiError",
    "allow_recipe_moderation",
    "api_bp",
    "cleanup_expired_otc_codes",
    "create_recipe",
    "create_registration_otc",
    "deactivate_recipe",
    "deactivate_user",
    "delete_recipe",
    "demote_user",
    "pending_recipe_moderation_count",
    "promote_user",
    "reactivate_recipe",
    "reactivate_user",
    "record_recipe_score",
    "register_user",
    "retest_all_recipe_moderation",
    "submit_creator_request",
    "toggle_recipe_favorite",
    "update_profile",
    "update_recipe",
]
