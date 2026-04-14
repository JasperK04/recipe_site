import io

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from PIL import Image
from sqlalchemy import or_

from app import db
from app.forms import RecipeForm
from app.models import KitchenMachine, Recipe

recipes_bp = Blueprint("recipes", __name__)


@recipes_bp.route("/")
def list_recipes():
    """Display all recipes."""
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", None)
    search = request.args.get("search", "")
    filter_by_machines = request.args.get("filter_machines", "0")

    query = Recipe.query.filter_by(status="public")

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
    # Only public recipes are viewable by others. Authors can view their own drafts.
    if recipe.status != "public":
        if not current_user.is_authenticated or current_user.id != recipe.user_id:
            abort(404)
    return render_template("recipes/view.html", recipe=recipe)


@recipes_bp.route("/<int:recipe_id>/image")
def recipe_image(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if not recipe.image_data:
        abort(404)
    return (recipe.image_data, 200, {"Content-Type": recipe.image_mime or "image/webp"})


@recipes_bp.route("/<int:recipe_id>/favorite", methods=["POST"])
@login_required
def favorite_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
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
    form = RecipeForm()

    # Populate kitchen machines choices
    machines = KitchenMachine.query.order_by(KitchenMachine.name).all()
    form.required_machines.choices = [(m.id, m.name) for m in machines]

    if form.validate_on_submit():
        # sanitize ingredient entries: keep only non-empty name or any value
        raw_ingredients = form.ingredients.data or []
        ingredients = []
        for ing in raw_ingredients:
            name = (ing.get("name_") or "").strip()
            qty_raw = (ing.get("quantity") or "").strip()
            measurement = (ing.get("measurement") or "").strip()
            if not name and not qty_raw and not measurement:
                continue
            # try to parse quantity to float, otherwise keep as string
            quantity = None
            if qty_raw:
                try:
                    quantity = float(qty_raw)
                except Exception:
                    quantity = qty_raw
            ingredients.append(
                {"name": name, "quantity": quantity, "measurement": measurement}
            )

        recipe = Recipe(
            title=form.title.data,  # type: ignore
            description=form.description.data,  # type: ignore
            ingredients=form.ingredients.data,  # type: ignore
            instructions=form.instructions.data,  # type: ignore
            prep_time=form.prep_time.data,  # type: ignore
            cook_time=form.cook_time.data,  # type: ignore
            servings=form.servings.data,  # type: ignore
            category=form.category.data if form.category.data else None,  # type: ignore
            status=form.status.data if getattr(form, "status", None) else "public",
            user_id=current_user.id,  # type: ignore
        )

        # Add required kitchen machines
        selected_machine_ids = form.required_machines.data
        if selected_machine_ids:
            selected_machines = KitchenMachine.query.filter(
                KitchenMachine.id.in_(selected_machine_ids)
            ).all()
            recipe.required_machines = selected_machines  # type: ignore

        db.session.add(recipe)
        # handle uploaded image (convert to webp before storing)
        if getattr(form, "image", None) and form.image.data:
            try:
                file_storage = form.image.data
                file_storage.stream.seek(0)
                img = Image.open(file_storage.stream)
                webp_bytes = io.BytesIO()
                img.convert("RGBA" if img.mode in ("RGBA", "LA") else "RGB").save(
                    webp_bytes, format="WEBP"
                )
                recipe.image_data = webp_bytes.getvalue()
                recipe.image_mime = "image/webp"
            except Exception:
                pass
        db.session.commit()
        flash("Recept succesvol toegevoegd!", "success")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))

    return render_template("recipes/form.html", form=form, title="Recept toevoegen")


@recipes_bp.route("/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
def edit_recipe(recipe_id):
    """Edit an existing recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)

    # Only the author can edit their recipe
    if recipe.user_id != current_user.id:
        abort(403)

    # Build a fresh form instance and populate scalar fields and FieldLists
    form = RecipeForm()

    # Populate kitchen machines choices
    machines = KitchenMachine.query.order_by(KitchenMachine.name).all()
    form.required_machines.choices = [(m.id, m.name) for m in machines]

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
                    "name_": ing.get("name_", ""),
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
        # sanitize as in add_recipe
        raw_ingredients = form.ingredients.data or []
        ingredients = []
        for ing in raw_ingredients:
            name = (ing.get("name_") or "").strip()
            qty_raw = (ing.get("quantity") or "").strip()
            measurement = (ing.get("measurement") or "").strip()
            if not name and not qty_raw and not measurement:
                continue
            try:
                quantity = float(qty_raw) if qty_raw else None
            except Exception:
                quantity = qty_raw
            ingredients.append(
                {"name_": name, "quantity": quantity, "measurement": measurement}
            )

        raw_steps = form.instructions.data or []
        instructions = [step for step in raw_steps if step.strip()]

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
            recipe.status = form.status.data

        # Update required kitchen machines
        selected_machine_ids = form.required_machines.data
        if selected_machine_ids:
            selected_machines = KitchenMachine.query.filter(
                KitchenMachine.id.in_(selected_machine_ids)
            ).all()
            recipe.required_machines = selected_machines
        else:
            recipe.required_machines = []

        # handle uploaded image replacement
        if getattr(form, "image", None) and form.image.data:
            try:
                file_storage = form.image.data
                file_storage.stream.seek(0)
                img = Image.open(file_storage.stream)
                webp_bytes = io.BytesIO()
                img.convert("RGBA" if img.mode in ("RGBA", "LA") else "RGB").save(
                    webp_bytes, format="WEBP"
                )
                recipe.image_data = webp_bytes.getvalue()
                recipe.image_mime = "image/webp"
            except Exception:
                pass

        # handle image removal requested by the form
        if request.form.get("remove_image") == "1":
            recipe.image_data = None
            recipe.image_mime = None

        db.session.commit()
        flash("Recept succesvol bijgewerkt!", "success")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))

    return render_template(
        "recipes/form.html", form=form, title="Recept bewerken", recipe=recipe
    )


@recipes_bp.route("/<int:recipe_id>/delete", methods=["POST"])
@login_required
def delete_recipe(recipe_id):
    """Delete a recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)

    # Only the author can delete their recipe
    if recipe.user_id != current_user.id:
        abort(403)

    db.session.delete(recipe)
    db.session.commit()
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
    recipes = current_user.favorites.order_by(Recipe.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    return render_template("recipes/favorites.html", recipes=recipes)
