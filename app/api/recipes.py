from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from flask import abort, jsonify, request, url_for
from flask_login import current_user, login_required

from app import db
from app.api import api_bp
from app.api.common import ApiError
from app.forms import RecipeForm
from app.image_store import delete_recipe_image, save_recipe_image
from app.models import Recipe, RecipeScore, User
from utils import require_active_admin, require_active_creator
from utils import (
    normalize_choice,
    sanitize_recipe_ingredients,
    sanitize_recipe_instructions,
)


def create_recipe(
    *,
    author: User,
    title: str,
    description: str | None,
    ingredients: list[str] | None,
    instructions: Iterable[str] | None,
    prep_time: int | None,
    cook_time: int | None,
    servings: int | None,
    category: str | None,
    status: str | None,
    image_file: Any = None,
) -> Recipe:
    """Create a recipe and persist the optional image."""
    recipe = Recipe(
        title=title,
        description=description,
        ingredients=sanitize_recipe_ingredients(ingredients),
        instructions=sanitize_recipe_instructions(instructions),
        prep_time=prep_time,
        cook_time=cook_time,
        servings=servings,
        category=category if category else None,
        status=normalize_choice(
            status,
            allowed=(Recipe.STATUS_DRAFT, Recipe.STATUS_PUBLIC),
            default=Recipe.STATUS_DRAFT,
        ),
        user_id=author.id,
    )

    db.session.add(recipe)
    uploaded_image_id = None
    if image_file:
        try:
            uploaded_image_id = save_recipe_image(image_file)
            recipe.image_id = uploaded_image_id
        except Exception:
            pass

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        if uploaded_image_id:
            delete_recipe_image(uploaded_image_id)
        raise

    return recipe


@api_bp.route("/recipes", methods=["POST"])
@login_required
def create_recipe_endpoint():
    user = cast(User, current_user)
    require_active_creator(user)
    form = RecipeForm()
    if not form.validate_on_submit():
        return jsonify({"status": "error", "message": "Controleer de invoer.", "errors": form.errors}), 400

    recipe = create_recipe(
        author=user,
        title=form.title.data,  # type: ignore[arg-type]
        description=form.description.data,  # type: ignore[arg-type]
        ingredients=form.ingredients.data,
        instructions=form.instructions.data,
        prep_time=form.prep_time.data,
        cook_time=form.cook_time.data,
        servings=form.servings.data,
        category=form.category.data if form.category.data else None,
        status=form.status.data,
        image_file=form.image.data if getattr(form, "image", None) and form.image.data else None,
    )
    return jsonify({"status": "ok", "redirect_url": url_for("recipes.view_recipe", recipe_id=recipe.id)})


def update_recipe(
    *,
    recipe: Recipe,
    title: str,
    description: str | None,
    ingredients: list[str] | None,
    instructions: Iterable[str] | None,
    prep_time: int | None,
    cook_time: int | None,
    servings: int | None,
    category: str | None,
    status: str | None,
    image_file: Any = None,
    remove_image: bool = False,
) -> Recipe:
    """Update a recipe and handle image replacement/removal."""
    recipe.title = title
    recipe.description = description
    recipe.ingredients = sanitize_recipe_ingredients(ingredients)
    recipe.instructions = sanitize_recipe_instructions(instructions)
    recipe.prep_time = prep_time
    recipe.cook_time = cook_time
    recipe.servings = servings
    recipe.category = category if category else None

    if status is not None:
        recipe.status = normalize_choice(
            status,
            allowed=(Recipe.STATUS_DRAFT, Recipe.STATUS_PUBLIC),
            default=recipe.status,
        )

    previous_image_id = recipe.image_id
    image_ids_to_delete_after_commit: set[str] = set()
    uploaded_image_id = None

    if image_file:
        try:
            uploaded_image_id = save_recipe_image(image_file)
            recipe.image_id = uploaded_image_id
            if previous_image_id:
                image_ids_to_delete_after_commit.add(previous_image_id)
        except Exception:
            pass

    if remove_image:
        if recipe.image_id:
            image_ids_to_delete_after_commit.add(recipe.image_id)
        recipe.image_id = None

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        if uploaded_image_id:
            delete_recipe_image(uploaded_image_id)
        raise

    for image_id in image_ids_to_delete_after_commit:
        if image_id != recipe.image_id:
            delete_recipe_image(image_id)

    return recipe


@api_bp.route("/recipes/<int:recipe_id>", methods=["POST"])
@login_required
def update_recipe_endpoint(recipe_id):
    user = cast(User, current_user)
    require_active_creator(user)
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.user_id != user.id:
        abort(403)
    if recipe.status == Recipe.STATUS_DEACTIVATED:
        abort(403)

    form = RecipeForm()
    if not form.validate_on_submit():
        return jsonify({"status": "error", "message": "Controleer de invoer.", "errors": form.errors}), 400

    updated = update_recipe(
        recipe=recipe,
        title=form.title.data,  # type: ignore[arg-type]
        description=form.description.data,  # type: ignore[arg-type]
        ingredients=form.ingredients.data,
        instructions=form.instructions.data,
        prep_time=form.prep_time.data,
        cook_time=form.cook_time.data,
        servings=form.servings.data,
        category=form.category.data if form.category.data else None,
        status=form.status.data,
        image_file=form.image.data if getattr(form, "image", None) and form.image.data else None,
        remove_image=request.form.get("remove_image") == "1",
    )
    return jsonify({"status": "ok", "redirect_url": url_for("recipes.view_recipe", recipe_id=updated.id)})


def delete_recipe(recipe: Recipe) -> str | None:
    """Delete a recipe and remove the backing image after commit."""
    image_id = recipe.image_id
    db.session.delete(recipe)
    db.session.commit()
    delete_recipe_image(image_id)
    return image_id


@api_bp.route("/recipes/<int:recipe_id>/delete", methods=["POST"])
@login_required
def delete_recipe_endpoint(recipe_id):
    user = cast(User, current_user)
    require_active_creator(user)
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.user_id != user.id:
        abort(403)

    delete_recipe(recipe)
    return jsonify({"status": "ok", "redirect_url": url_for("recipes.list_recipes")})


def toggle_recipe_favorite(*, user: User, recipe: Recipe, favorite: bool) -> bool:
    """Add or remove a recipe from the user's favorites."""
    if recipe.status != Recipe.STATUS_PUBLIC:
        raise ApiError("Alleen openbare recepten kunnen worden gefavoriet.", 403)

    existing = user.favorites.filter_by(id=recipe.id).first()
    changed = False

    if favorite and not existing:
        user.favorites.append(recipe)
        changed = True
    elif not favorite and existing:
        user.favorites.remove(recipe)
        changed = True

    if changed:
        db.session.commit()

    return changed


@api_bp.route("/recipes/<int:recipe_id>/favorite", methods=["POST"])
@login_required
def favorite_recipe_endpoint(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    user = cast(User, current_user)
    try:
        created = toggle_recipe_favorite(user=user, recipe=recipe, favorite=True)
    except ApiError as error:
        return jsonify({"status": "error", "message": error.message}), error.status_code
    return jsonify({"status": "ok", "favorited": created})


@api_bp.route("/recipes/<int:recipe_id>/unfavorite", methods=["POST"])
@login_required
def unfavorite_recipe_endpoint(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    user = cast(User, current_user)
    try:
        removed = toggle_recipe_favorite(user=user, recipe=recipe, favorite=False)
    except ApiError as error:
        return jsonify({"status": "error", "message": error.message}), error.status_code
    return jsonify({"status": "ok", "favorited": not removed})


def record_recipe_score(
    *, user: User, recipe: Recipe, score_value: int
) -> dict[str, Any]:
    """Create or update a user's recipe score and return fresh stats."""
    if current_user_is_owner(user, recipe):
        raise ApiError("U kunt uw eigen recept niet beoordelen.", 403)

    if recipe.status != Recipe.STATUS_PUBLIC:
        raise ApiError("Alleen openbare recepten kunnen worden beoordeeld.", 403)

    if score_value not in [1, 2, 3, 4, 5]:
        raise ApiError("Score moet tussen 1 en 5 liggen.", 400)

    existing = RecipeScore.query.filter_by(recipe_id=recipe.id, user_id=user.id).first()
    if existing:
        existing.score = score_value
    else:
        db.session.add(
            RecipeScore(recipe_id=recipe.id, user_id=user.id, score=score_value)
        )

    db.session.commit()
    return {
        "score": score_value,
        "score_average": recipe.score_average,
        "score_count": recipe.score_count,
    }


@api_bp.route("/recipes/<int:recipe_id>/score", methods=["POST"])
@login_required
def score_recipe_endpoint(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if not recipe.is_visible_to(current_user):
        abort(404)
    if not current_user.can_score_recipes:
        abort(403)
    user = cast(User, current_user)

    try:
        score_value = request.form.get("score", type=int)
        if score_value is None:
            abort(400)
        stats = record_recipe_score(
            user=user,
            recipe=recipe,
            score_value=score_value,
        )
    except ApiError as error:
        return jsonify({"status": "error", "message": error.message}), error.status_code

    return jsonify({"status": "ok", **stats})


def deactivate_recipe(recipe: Recipe) -> Recipe:
    """Mark a recipe as deactivated."""
    if recipe.status != Recipe.STATUS_DEACTIVATED:
        recipe.status_before_deactivation = recipe.status
        recipe.status = Recipe.STATUS_DEACTIVATED
        db.session.commit()
    return recipe


@api_bp.route("/recipes/<int:recipe_id>/deactivate", methods=["POST"])
@login_required
def deactivate_recipe_endpoint(recipe_id):
    require_active_admin(current_user)
    recipe = Recipe.query.get_or_404(recipe_id)
    deactivate_recipe(recipe)
    return jsonify({"status": "ok", "new_status": recipe.status})


def reactivate_recipe(recipe: Recipe) -> Recipe:
    """Restore a previously deactivated recipe."""
    if recipe.status == Recipe.STATUS_DEACTIVATED:
        if recipe.status_before_deactivation in (
            Recipe.STATUS_PUBLIC,
            Recipe.STATUS_DRAFT,
        ):
            recipe.status = recipe.status_before_deactivation
        else:
            recipe.status = Recipe.STATUS_DRAFT
        recipe.status_before_deactivation = None
        db.session.commit()
    return recipe


@api_bp.route("/recipes/<int:recipe_id>/reactivate", methods=["POST"])
@login_required
def reactivate_recipe_endpoint(recipe_id):
    require_active_admin(current_user)
    recipe = Recipe.query.get_or_404(recipe_id)
    reactivate_recipe(recipe)
    return jsonify({"status": "ok", "new_status": recipe.status})


def current_user_is_owner(user: User, recipe: Recipe) -> bool:
    return bool(user.is_authenticated and user.id == recipe.user_id)
