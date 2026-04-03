from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
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
    filter_by_machines = request.args.get(
        "filter_machines", "1" if current_user.is_authenticated else "0"
    )

    query = Recipe.query

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

    # Filter by user's available kitchen machines (default on for authenticated users)
    if current_user.is_authenticated and filter_by_machines == "1":
        user_machine_ids = [m.id for m in current_user.kitchen_machines]
        if user_machine_ids:
            # Only show recipes where all required machines are in user's collection
            # or recipes with no required machines
            query = query.filter(
                or_(
                    ~Recipe.required_machines.any(),  # No required machines
                    Recipe.id.in_(  # All required machines are available
                        db.session.query(Recipe.id)
                        .join(Recipe.required_machines)  # type: ignore
                        .group_by(Recipe.id)
                        .having(
                            db.func.count(KitchenMachine.id)
                            == db.func.sum(
                                db.case(
                                    (KitchenMachine.id.in_(user_machine_ids), 1),
                                    else_=0,
                                )
                            )
                        )
                    ),
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
        filter_by_machines=filter_by_machines,
    )


@recipes_bp.route("/<int:recipe_id>")
def view_recipe(recipe_id):
    """View a single recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)
    return render_template("recipes/view.html", recipe=recipe)


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

        # Update required kitchen machines
        selected_machine_ids = form.required_machines.data
        if selected_machine_ids:
            selected_machines = KitchenMachine.query.filter(
                KitchenMachine.id.in_(selected_machine_ids)
            ).all()
            recipe.required_machines = selected_machines
        else:
            recipe.required_machines = []

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
