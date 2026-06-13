from flask import Blueprint, render_template

from app.models import Recipe

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Home page displaying recent recipes."""
    recent_recipes = (
        Recipe.query.filter_by(status=Recipe.STATUS_PUBLIC)
        .order_by(Recipe.created_at.desc())
        .limit(12)
        .all()
    )
    return render_template("index.html", recipes=recent_recipes)


@main_bp.route("/about")
def about():
    """About page."""
    return render_template("about.html")
