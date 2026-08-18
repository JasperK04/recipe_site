from flask import Blueprint, render_template, request
from sqlalchemy import func

from app import db
from app.models import Recipe, RecipeScore

main_bp = Blueprint("main", __name__)

HOME_SORT_OPTIONS = {
    "newest": "Nieuw naar oud",
    "oldest": "Oud naar nieuw",
    "rating_desc": "Hoogste beoordeling",
    "rating_asc": "Laagste beoordeling",
}


def _apply_home_sort(query, sort_key: str):
    average_score = (
        db.session.query(func.coalesce(func.avg(RecipeScore.score), 0.0))
        .filter(RecipeScore.recipe_id == Recipe.id)
        .correlate(Recipe)
        .scalar_subquery()
    )
    score_count = (
        db.session.query(func.count(RecipeScore.id))
        .filter(RecipeScore.recipe_id == Recipe.id)
        .correlate(Recipe)
        .scalar_subquery()
    )

    if sort_key == "oldest":
        return query.order_by(Recipe.created_at.asc())
    if sort_key == "rating_desc":
        return query.order_by(
            average_score.desc(), score_count.desc(), Recipe.created_at.desc()
        )
    if sort_key == "rating_asc":
        return query.order_by(
            average_score.asc(), score_count.asc(), Recipe.created_at.asc()
        )
    return query.order_by(Recipe.created_at.desc())


@main_bp.route("/")
def index():
    """Home page displaying recent recipes."""
    sort = request.args.get("sort", "newest").strip().lower()
    if sort not in HOME_SORT_OPTIONS:
        sort = "newest"

    query = Recipe.query.filter_by(status=Recipe.STATUS_PUBLIC)
    recent_recipes = _apply_home_sort(query, sort).limit(12).all()
    return render_template(
        "index.html",
        recipes=recent_recipes,
        sort=sort,
        sort_options=HOME_SORT_OPTIONS,
    )


@main_bp.route("/about")
def about():
    """About page."""
    return render_template("about.html")
