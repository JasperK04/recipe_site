import json
from typing import cast

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.api import (
    ApiError,
    create_recipe,
    record_recipe_score,
    toggle_recipe_favorite,
)
from app.api import (
    delete_recipe as api_delete_recipe,
)
from app.api import (
    update_recipe as api_update_recipe,
)
from app.forms import RecipeForm, RecipeUploadForm
from app.image_store import read_recipe_image_bytes
from app.models import Recipe, User
from utils import (
    ingredient_to_string,
    require_active_creator,
    sanitize_recipe_ingredients,
)
from utils.upload import parse_uploaded_text, read_uploaded_page, validate_uploaded_json

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

    recipes = query.order_by(Recipe.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    return render_template(
        "recipes/list.html",
        recipes=recipes,
        category=category,
        search=search,
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
    user = cast(User, current_user)
    created = False
    try:
        created = toggle_recipe_favorite(user=user, recipe=recipe, favorite=True)
    except ApiError as error:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(
                {"status": "error", "message": error.message}
            ), error.status_code
        abort(error.status_code)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "ok", "favorited": created})

    return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))


@recipes_bp.route("/<int:recipe_id>/unfavorite", methods=["POST"])
@login_required
def unfavorite_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    user = cast(User, current_user)
    removed = False
    try:
        removed = toggle_recipe_favorite(user=user, recipe=recipe, favorite=False)
    except ApiError as error:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(
                {"status": "error", "message": error.message}
            ), error.status_code
        abort(error.status_code)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "ok", "favorited": not removed})

    return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))


@recipes_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_recipe():
    """Add a new recipe."""
    require_active_creator(current_user)
    user = cast(User, current_user)
    validate_on_load = request.args.get("source") == "upload"
    if request.method == "GET" and request.args.get("title"):
        form = RecipeForm(
            data={
                "title": request.args.get("title"),
                "description": request.args.get("description"),
                "prep_time": request.args.get("prep_time"),
                "cook_time": request.args.get("cook_time"),
                "total_time": request.args.get("total_time"),
                "servings": request.args.get("servings"),
                "ingredients": sanitize_recipe_ingredients(
                    json.loads(request.args.get("ingredients", "[]")),
                    plain_text=True,
                ),
                "instructions": json.loads(request.args.get("instructions", "[]")),
                "category": request.args.get("category"),
            }
        )
    else:
        form = RecipeForm()

    if form.validate_on_submit():
        try:
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
                image_file=form.image.data
                if getattr(form, "image", None) and form.image.data
                else None,
            )
        except ApiError as error:
            flash(error.message, "danger")
            return render_template(
                "recipes/form.html",
                form=form,
                title="Recept toevoegen",
                validate_on_load=validate_on_load,
            )

        if recipe.status == Recipe.STATUS_PUBLIC:
            flash("Recept succesvol gepubliceerd!", "success")
        else:
            flash("Concept opgeslagen.", "success")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))

    return render_template(
        "recipes/form.html",
        form=form,
        title="Recept toevoegen",
        validate_on_load=validate_on_load,
    )


@recipes_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload_recipe():
    """Add a new recipe."""
    require_active_creator(current_user)
    form = RecipeUploadForm()

    def flash_(message, category="info"):
        flash(message, category)
        return render_template(
            "recipes/upload.html", form=form, title="Recept uploaden"
        )

    if form.validate_on_submit():
        match form.upload_type.data:
            case "url":
                if not form.url.data:
                    return flash_("URL is vereist voor deze uploadmethode.", "danger")
                data = read_uploaded_page(form.url.data)
            case "textarea":
                if not form.textarea.data:
                    return flash_("Tekst is vereist voor deze uploadmethode.", "danger")
                data = parse_uploaded_text(form.textarea.data)
            case "text":
                if not form.text_file.data:
                    return flash_(
                        "Tekstbestand is vereist voor deze uploadmethode.", "danger"
                    )
                data = parse_uploaded_text(form.text_file.data.read().decode("utf-8"))
            case "json":
                if not form.json_file.data:
                    return flash_(
                        "JSON-bestand is vereist voor deze uploadmethode.", "danger"
                    )
                data = validate_uploaded_json(
                    json.load(form.json_file.data),
                    required_keys=["name", "ingredients", "instructions"],
                )
            case _:
                return flash_("Ongeldig uploadtype geselecteerd.", "danger")

        return redirect(
            url_for(
                "recipes.add_recipe",
                source="upload",
                title=data.get("name", ""),
                description=data.get("description", ""),
                prep_time=data.get("prep_time", ""),
                cook_time=data.get("cook_time", ""),
                total_time=data.get("total_time", ""),
                servings=data.get("servings", ""),
                ingredients=json.dumps(data.get("ingredients", [])),
                instructions=json.dumps(data.get("instructions", [])),
                category=data.get("category", ""),
            )
        )
    return render_template("recipes/upload.html", form=form, title="Recept uploaden")


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

        try:
            form.ingredients.entries.clear()
        except Exception:
            pass

        for ing in recipe.ingredients:
            form.ingredients.append_entry(ingredient_to_string(ing))

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
        try:
            recipe = api_update_recipe(
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
                image_file=form.image.data
                if getattr(form, "image", None) and form.image.data
                else None,
                remove_image=request.form.get("remove_image") == "1",
            )
        except ApiError as error:
            flash(error.message, "danger")
            return render_template(
                "recipes/form.html",
                form=form,
                title="Recept bewerken",
                recipe=recipe,
                validate_on_load=False,
            )

        if recipe.status == Recipe.STATUS_PUBLIC:
            flash("Recept succesvol bijgewerkt en gepubliceerd.", "success")
        else:
            flash("Concept succesvol bijgewerkt.", "success")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))

    return render_template(
        "recipes/form.html",
        form=form,
        title="Recept bewerken",
        recipe=recipe,
        validate_on_load=False,
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

    api_delete_recipe(recipe)
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
    score_value = request.form.get("score", type=int)
    if score_value is None:
        abort(400)
    user = cast(User, current_user)
    try:
        stats = record_recipe_score(
            user=user, recipe=recipe, score_value=int(score_value)
        )
    except ApiError as error:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(
                {"status": "error", "message": error.message}
            ), error.status_code
        flash(error.message, "danger")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "ok", **stats})
    return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))
