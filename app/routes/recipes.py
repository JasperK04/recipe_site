from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from typing import cast

from app import db
from app.forms import RecipeForm
from app.image_store import (
    delete_recipe_image,
    read_recipe_image_bytes,
    save_recipe_image,
)
from app.models import KitchenMachine, Recipe, RecipeScore
from utils import (
    normalize_choice,
    query_rows_by_ids,
    require_active_admin,
    require_active_creator,
    sanitize_recipe_ingredients,
    sanitize_recipe_instructions,
    to_model_choices,
)

recipes_bp = Blueprint("recipes", __name__)


def _status_badge(status):
    if status == Recipe.STATUS_DRAFT:
        return ("Concept", "warning text-dark")
    if status == Recipe.STATUS_DEACTIVATED:
        return ("Gedeactiveerd", "danger")
    return ("Openbaar", "success")


@recipes_bp.route("/")
def list_recipes():
    """Display public recipes."""
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", None)
    search = request.args.get("search", "")
    filter_by_machines = request.args.get("filter_machines", "0")

    query = Recipe.query.filter_by(status=Recipe.STATUS_PUBLIC)

    if category:
        query = query.filter_by(category=category)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Recipe.title.ilike(search_pattern),
                Recipe.description.ilike(search_pattern),
            )
        )

    # No per-user machine filtering (assume users have needed machines)

    recipes = query.order_by(Recipe.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    return render_template(
        "recipes/list.html",
        recipes=recipes,
        category=category,
        search=search,
        filter_by_machines=filter_by_machines,
    )


@recipes_bp.route("/<int:recipe_id>")
def view_recipe(recipe_id):
    """View a single recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)
    if not recipe.is_visible_to(current_user):
        abort(404)

    my_score = None
    if current_user.is_authenticated:
        my_score = recipe.score_for_user(current_user.id)

    can_edit_recipe = (
        current_user.is_authenticated
        and current_user.id == recipe.user_id
        and current_user.can_create_recipes
        and recipe.status != Recipe.STATUS_DEACTIVATED
    )
    can_moderate_recipe = (
        current_user.is_authenticated
        and current_user.is_active
        and current_user.is_admin
    )
    can_score_recipe = (
        current_user.is_authenticated
        and current_user.can_score_recipes
        and recipe.status == Recipe.STATUS_PUBLIC
    )
    status_label, status_badge_class = _status_badge(recipe.status)

    return render_template(
        "recipes/view.html",
        recipe=recipe,
        can_edit_recipe=can_edit_recipe,
        can_moderate_recipe=can_moderate_recipe,
        can_score_recipe=can_score_recipe,
        my_score=my_score,
        status_label=status_label,
        status_badge_class=status_badge_class,
    )


@recipes_bp.route("/<int:recipe_id>/image")
def recipe_image(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if not recipe.is_visible_to(current_user):
        abort(404)
    image_data = read_recipe_image_bytes(recipe.image_id)
    if not image_data:
        abort(404)
    return (image_data, 200, {"Content-Type": "image/webp"})


@recipes_bp.route("/<int:recipe_id>/favorite", methods=["POST"])
@login_required
def favorite_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.status != Recipe.STATUS_PUBLIC:
        abort(403)
    # add to favorites if not already present
    if not current_user.favorites.filter_by(id=recipe.id).first():
        current_user.favorites.append(recipe)
        db.session.commit()
        flash("Toegevoegd aan favorieten", "success")
    else:
        flash("Recept staat al in favorieten", "info")
    return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))


@recipes_bp.route("/<int:recipe_id>/unfavorite", methods=["POST"])
@login_required
def unfavorite_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.status != Recipe.STATUS_PUBLIC:
        abort(403)
    if current_user.favorites.filter_by(id=recipe.id).first():
        current_user.favorites.remove(recipe)
        db.session.commit()
        flash("Verwijderd uit favorieten", "success")
    else:
        flash("Recept stond niet in favorieten", "info")
    return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))


@recipes_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_recipe():
    """Add a new recipe."""
    require_active_creator(current_user)
    form = RecipeForm()

    # Populate kitchen machines choices
    machines = KitchenMachine.query.order_by(KitchenMachine.name).all()
    form.required_machines.choices = to_model_choices(machines)

    if form.validate_on_submit():
        ingredients = sanitize_recipe_ingredients(form.ingredients.data)
        instructions = sanitize_recipe_instructions(form.instructions.data)
        requested_status = normalize_choice(
            form.status.data,
            allowed=(Recipe.STATUS_DRAFT, Recipe.STATUS_PUBLIC),
            default=Recipe.STATUS_DRAFT,
        )

        recipe = Recipe(
            title=form.title.data,  # type: ignore
            description=form.description.data,  # type: ignore
            ingredients=ingredients,
            instructions=instructions,
            prep_time=form.prep_time.data,  # type: ignore
            cook_time=form.cook_time.data,  # type: ignore
            servings=form.servings.data,  # type: ignore
            category=form.category.data if form.category.data else None,  # type: ignore
            status=requested_status,
            user_id=current_user.id,  # type: ignore
        )

        # Add required kitchen machines
        recipe.required_machines = cast(  # pyright: ignore[reportAttributeAccessIssue]
            list[KitchenMachine],
            query_rows_by_ids(KitchenMachine, form.required_machines.data),
        )

        db.session.add(recipe)
        uploaded_image_id = None
        # Handle uploaded image (store as DATAROOT/recipe/<image_id>.webp).
        if getattr(form, "image", None) and form.image.data:
            try:
                uploaded_image_id = save_recipe_image(form.image.data)
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
        if recipe.status == Recipe.STATUS_PUBLIC:
            flash("Recept succesvol gepubliceerd!", "success")
        else:
            flash("Concept opgeslagen.", "success")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))

    return render_template("recipes/form.html", form=form, title="Recept toevoegen")


@recipes_bp.route("/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
def edit_recipe(recipe_id):
    """Edit an existing recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)
    require_active_creator(current_user)

    # Only the author can edit their recipe
    if recipe.user_id != current_user.id:
        abort(403)
    if recipe.status == Recipe.STATUS_DEACTIVATED:
        abort(403)

    # Build a fresh form instance and populate scalar fields and FieldLists
    form = RecipeForm()

    # Populate kitchen machines choices
    machines = KitchenMachine.query.order_by(KitchenMachine.name).all()
    form.required_machines.choices = to_model_choices(machines)

    if request.method == "GET":
        # simple fields
        form.title.data = recipe.title
        form.description.data = recipe.description
        # status
        try:
            form.status.data = recipe.status
        except Exception:
            pass
        form.prep_time.data = recipe.prep_time
        form.cook_time.data = recipe.cook_time
        form.servings.data = recipe.servings
        form.category.data = recipe.category if recipe.category else ""

        # Pre-populate required machines
        form.required_machines.data = [m.id for m in recipe.required_machines]

        # populate ingredients FieldList
        try:
            form.ingredients.entries.clear()
        except Exception:
            pass
        for ing in recipe.ingredients or []:
            form.ingredients.append_entry(
                {
                    "name_": ing.get("name_", ing.get("name", "")),
                    "quantity": str(ing.get("quantity", "") or ""),
                    "measurement": ing.get("measurement", "") or "",
                }
            )
        if len(form.ingredients.entries) == 0:
            form.ingredients.append_entry()

        # populate instructions FieldList
        try:
            form.instructions.entries.clear()
        except Exception:
            pass
        for step in recipe.instructions or []:
            form.instructions.append_entry(step)
        if len(form.instructions.entries) == 0:
            form.instructions.append_entry()
    if form.validate_on_submit():
        ingredients = sanitize_recipe_ingredients(form.ingredients.data)
        instructions = sanitize_recipe_instructions(form.instructions.data)

        recipe.title = form.title.data
        recipe.description = form.description.data
        recipe.ingredients = ingredients
        recipe.instructions = instructions
        recipe.prep_time = form.prep_time.data
        recipe.cook_time = form.cook_time.data
        recipe.servings = form.servings.data
        recipe.category = form.category.data if form.category.data else None
        # status update
        if getattr(form, "status", None):
            recipe.status = normalize_choice(
                form.status.data,
                allowed=(Recipe.STATUS_DRAFT, Recipe.STATUS_PUBLIC),
                default=recipe.status,
            )

        # Update required kitchen machines
        recipe.required_machines = cast(  # pyright: ignore[reportAttributeAccessIssue]
            list[KitchenMachine],
            query_rows_by_ids(KitchenMachine, form.required_machines.data),
        )

        previous_image_id = recipe.image_id
        image_ids_to_delete_after_commit = set()
        uploaded_image_id = None

        # handle uploaded image replacement
        if getattr(form, "image", None) and form.image.data:
            try:
                uploaded_image_id = save_recipe_image(form.image.data)
                recipe.image_id = uploaded_image_id
                if previous_image_id:
                    image_ids_to_delete_after_commit.add(previous_image_id)
            except Exception:
                pass

        # handle image removal requested by the form
        if request.form.get("remove_image") == "1":
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
        if recipe.status == Recipe.STATUS_PUBLIC:
            flash("Recept succesvol bijgewerkt en gepubliceerd.", "success")
        else:
            flash("Concept succesvol bijgewerkt.", "success")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))

    return render_template(
        "recipes/form.html", form=form, title="Recept bewerken", recipe=recipe
    )


@recipes_bp.route("/<int:recipe_id>/delete", methods=["POST"])
@login_required
def delete_recipe(recipe_id):
    """Delete a recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)
    require_active_creator(current_user)

    # Only the author can delete their recipe
    if recipe.user_id != current_user.id:
        abort(403)

    image_id = recipe.image_id
    db.session.delete(recipe)
    db.session.commit()
    delete_recipe_image(image_id)
    flash("Recept succesvol verwijderd!", "success")
    return redirect(url_for("recipes.list_recipes"))


@recipes_bp.route("/my-recipes")
@login_required
def my_recipes():
    """Display current user's recipes."""
    page = request.args.get("page", 1, type=int)
    recipes = (
        Recipe.query.filter_by(user_id=current_user.id)
        .order_by(Recipe.created_at.desc())
        .paginate(page=page, per_page=12, error_out=False)
    )

    return render_template("recipes/my_recipes.html", recipes=recipes)


@recipes_bp.route("/favorites")
@login_required
def favorites():
    """Display current user's favorite recipes."""
    page = request.args.get("page", 1, type=int)
    recipes = (
        current_user.favorites.filter(Recipe.status == Recipe.STATUS_PUBLIC)
        .order_by(Recipe.created_at.desc())
        .paginate(page=page, per_page=12, error_out=False)
    )

    return render_template("recipes/favorites.html", recipes=recipes)


@recipes_bp.route("/<int:recipe_id>/score", methods=["POST"])
@login_required
def score_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if not recipe.is_visible_to(current_user):
        abort(404)
    if not current_user.can_score_recipes:
        abort(403)
    if recipe.status != Recipe.STATUS_PUBLIC:
        abort(403)

    score_value = request.form.get("score", type=int)
    if score_value not in [1, 2, 3, 4, 5]:
        flash("Score moet tussen 1 en 5 liggen.", "danger")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))

    existing = RecipeScore.query.filter_by(
        recipe_id=recipe.id, user_id=current_user.id
    ).first()
    if existing:
        existing.score = score_value
        flash("Je score is bijgewerkt.", "success")
    else:
        db.session.add(
            RecipeScore(recipe_id=recipe.id, user_id=current_user.id, score=score_value)
        )
        flash("Je score is opgeslagen.", "success")
    db.session.commit()
    return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))


@recipes_bp.route("/admin")
@login_required
def admin_recipes():
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
        page=page, per_page=20, error_out=False
    )
    return render_template(
        "recipes/admin_list.html", recipes=recipes, status=status, search=search
    )


@recipes_bp.route("/admin/<int:recipe_id>/deactivate", methods=["POST"])
@login_required
def deactivate_recipe(recipe_id):
    require_active_admin(current_user)
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.status == Recipe.STATUS_DEACTIVATED:
        flash("Recept is al gedeactiveerd.", "info")
        return redirect(request.referrer or url_for("recipes.admin_recipes"))

    recipe.status_before_deactivation = recipe.status
    recipe.status = Recipe.STATUS_DEACTIVATED
    db.session.commit()
    flash("Recept gedeactiveerd.", "success")
    return redirect(request.referrer or url_for("recipes.admin_recipes"))


@recipes_bp.route("/admin/<int:recipe_id>/reactivate", methods=["POST"])
@login_required
def reactivate_recipe(recipe_id):
    require_active_admin(current_user)
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.status != Recipe.STATUS_DEACTIVATED:
        flash("Recept is al actief.", "info")
        return redirect(request.referrer or url_for("recipes.admin_recipes"))

    if recipe.status_before_deactivation in (Recipe.STATUS_PUBLIC, Recipe.STATUS_DRAFT):
        recipe.status = recipe.status_before_deactivation
    else:
        recipe.status = Recipe.STATUS_DRAFT
    recipe.status_before_deactivation = None
    db.session.commit()
    flash("Recept opnieuw geactiveerd.", "success")
    return redirect(request.referrer or url_for("recipes.admin_recipes"))
