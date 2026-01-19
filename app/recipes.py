from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from app import db
from app.models import Recipe
from app.forms import RecipeForm

recipes_bp = Blueprint('recipes', __name__)


@recipes_bp.route('/')
def list_recipes():
    """Display all recipes."""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', None)
    search = request.args.get('search', '')
    
    query = Recipe.query
    
    if category:
        query = query.filter_by(category=category)
    
    if search:
        search_pattern = f'%{search}%'
        query = query.filter(or_(
            Recipe.title.ilike(search_pattern),
            Recipe.description.ilike(search_pattern)
        ))
    
    recipes = query.order_by(Recipe.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    
    return render_template('recipes/list.html', recipes=recipes, category=category, search=search)


@recipes_bp.route('/<int:recipe_id>')
def view_recipe(recipe_id):
    """View a single recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)
    return render_template('recipes/view.html', recipe=recipe)


@recipes_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_recipe():
    """Add a new recipe."""
    form = RecipeForm()
    if form.validate_on_submit():
        recipe = Recipe(
            title=form.title.data,
            description=form.description.data,
            ingredients=form.ingredients.data,
            instructions=form.instructions.data,
            prep_time=form.prep_time.data,
            cook_time=form.cook_time.data,
            servings=form.servings.data,
            category=form.category.data if form.category.data else None,
            user_id=current_user.id
        )
        db.session.add(recipe)
        db.session.commit()
        flash('Recipe added successfully!', 'success')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))
    
    return render_template('recipes/form.html', form=form, title='Add Recipe')


@recipes_bp.route('/<int:recipe_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    """Edit an existing recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)
    
    # Only the author can edit their recipe
    if recipe.user_id != current_user.id:
        abort(403)
    
    form = RecipeForm(obj=recipe)
    if form.validate_on_submit():
        recipe.title = form.title.data
        recipe.description = form.description.data
        recipe.ingredients = form.ingredients.data
        recipe.instructions = form.instructions.data
        recipe.prep_time = form.prep_time.data
        recipe.cook_time = form.cook_time.data
        recipe.servings = form.servings.data
        recipe.category = form.category.data if form.category.data else None
        db.session.commit()
        flash('Recipe updated successfully!', 'success')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))
    
    return render_template('recipes/form.html', form=form, title='Edit Recipe', recipe=recipe)


@recipes_bp.route('/<int:recipe_id>/delete', methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    """Delete a recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)
    
    # Only the author can delete their recipe
    if recipe.user_id != current_user.id:
        abort(403)
    
    db.session.delete(recipe)
    db.session.commit()
    flash('Recipe deleted successfully!', 'success')
    return redirect(url_for('recipes.list_recipes'))


@recipes_bp.route('/my-recipes')
@login_required
def my_recipes():
    """Display current user's recipes."""
    page = request.args.get('page', 1, type=int)
    recipes = Recipe.query.filter_by(user_id=current_user.id).order_by(
        Recipe.created_at.desc()
    ).paginate(page=page, per_page=12, error_out=False)
    
    return render_template('recipes/my_recipes.html', recipes=recipes)
