from flask import Blueprint, render_template
from app.models import Recipe

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Home page displaying recent recipes."""
    recent_recipes = Recipe.query.order_by(Recipe.created_at.desc()).limit(6).all()
    return render_template('index.html', recipes=recent_recipes)


@main_bp.route('/about')
def about():
    """About page."""
    return render_template('about.html')
