from __future__ import annotations

from typing import cast

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.api import (
    ApiError,
    deactivate_recipe,
    deactivate_user,
    demote_user,
    promote_user,
    reactivate_recipe,
    reactivate_user,
)
from app.models import Recipe, User
from utils import require_active_admin

admin_bp = Blueprint("admin", __name__)


def _user_row_response(user: User):
    return jsonify(
        {
            "status": "ok",
            "html": render_template(
                "components/user_table_row.html",
                user=user,
                current_user=current_user,
            ),
        }
    )


def _json_error(error: ApiError):
    return jsonify({"status": "error", "message": error.message}), error.status_code


@admin_bp.route("/users")
@login_required
def users():
    require_active_admin(current_user)
    users = User.query.order_by(db.text("is_active DESC"), User.username.asc()).all()
    return render_template("auth/admin_users.html", users=users)


@admin_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@login_required
def deactivate_user_route(user_id):
    admin_user = cast(User, current_user)
    require_active_admin(admin_user)
    target = User.query.get_or_404(user_id)

    try:
        deactivate_user(actor=admin_user, target=target)
    except ApiError as error:
        return _json_error(error)

    return _user_row_response(target)


@admin_bp.route("/users/<int:user_id>/reactivate", methods=["POST"])
@login_required
def reactivate_user_route(user_id):
    admin_user = cast(User, current_user)
    require_active_admin(admin_user)
    target = User.query.get_or_404(user_id)

    reactivate_user(target)
    return _user_row_response(target)


@admin_bp.route("/users/<int:user_id>/promote", methods=["POST"])
@login_required
def promote_user_route(user_id):
    admin_user = cast(User, current_user)
    require_active_admin(admin_user)
    target = User.query.get_or_404(user_id)

    try:
        promote_user(target)
    except ApiError as error:
        return _json_error(error)

    return _user_row_response(target)


@admin_bp.route("/users/<int:user_id>/demote", methods=["POST"])
@login_required
def demote_user_route(user_id):
    admin_user = cast(User, current_user)
    require_active_admin(admin_user)
    target = User.query.get_or_404(user_id)

    try:
        demote_user(target)
    except ApiError as error:
        return _json_error(error)

    return _user_row_response(target)


@admin_bp.route("/recipes")
@login_required
def recipes():
    require_active_admin(current_user)
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "all")
    search = request.args.get("search", "")

    query = Recipe.query
    if status in Recipe.VALID_STATUSES:
        query = query.filter_by(status=status)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Recipe.title.ilike(search_pattern),
                Recipe.description.ilike(search_pattern),
            )
        )
    recipes = query.order_by(Recipe.created_at.desc()).paginate(
        page=page, per_page=24, error_out=False
    )
    return render_template(
        "recipes/admin_list.html", recipes=recipes, status=status, search=search
    )


@admin_bp.route("/recipes/<int:recipe_id>/deactivate", methods=["POST"])
@login_required
def deactivate_recipe_route(recipe_id):
    require_active_admin(current_user)
    recipe = Recipe.query.get_or_404(recipe_id)
    already_deactivated = recipe.status == Recipe.STATUS_DEACTIVATED
    deactivate_recipe(recipe)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "ok", "new_status": recipe.status})
    if already_deactivated:
        flash("Recept is al gedeactiveerd.", "info")
    else:
        flash("Recept gedeactiveerd.", "success")
    return redirect(request.referrer or url_for("admin.recipes"))


@admin_bp.route("/recipes/<int:recipe_id>/reactivate", methods=["POST"])
@login_required
def reactivate_recipe_route(recipe_id):
    require_active_admin(current_user)
    recipe = Recipe.query.get_or_404(recipe_id)
    already_active = recipe.status != Recipe.STATUS_DEACTIVATED
    reactivate_recipe(recipe)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "ok", "new_status": recipe.status})
    if already_active:
        flash("Recept is al actief.", "info")
    else:
        flash("Recept opnieuw geactiveerd.", "success")
    return redirect(request.referrer or url_for("admin.recipes"))
