from flask import Blueprint, Response, render_template, request, url_for
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


@main_bp.route("/over")
def about():
    """About page."""
    return render_template("about.html")


@main_bp.route("/robots.txt")
def robots():
    body = "\n".join(
        [
            "User-agent: *",
            "Disallow: /admin/",
            "Disallow: /account/",
            "Disallow: /api/",
            "Disallow: /recept/toevoegen",
            "Disallow: /recept/uploaden",
            "Disallow: /recept/zoeken/",
            "Disallow: /recept/genest/",
            f"Sitemap: {url_for('main.sitemap', _external=True)}",
            "",
        ]
    )
    return Response(body, mimetype="text/plain")


@main_bp.route("/sitemap.xml")
def sitemap():
    static_urls = [
        (url_for("main.index", _external=True), None),
        (url_for("main.about", _external=True), None),
        (url_for("recipe_overview.list_recipes", _external=True), None),
    ]
    categories = [
        "Ontbijt",
        "Lunch",
        "Voorgerecht",
        "Hoofdgerecht",
        "Nagerecht",
        "Snack",
        "Drank",
        "Overig",
    ]
    static_urls.extend(
        (
            url_for("recipe_overview.list_recipes", category=category, _external=True),
            None,
        )
        for category in categories
    )
    recipes = (
        Recipe.query.filter_by(status=Recipe.STATUS_PUBLIC).order_by(Recipe.id).all()
    )
    urls = static_urls + [
        (
            url_for(
                "recipes.view_recipe",
                recipe_id=recipe.id,
                title=recipe.url_title,
                _external=True,
            ),
            recipe.updated_at or recipe.created_at,
        )
        for recipe in recipes
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for location, lastmod in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{location}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod.date().isoformat()}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return Response("\n".join(lines), mimetype="application/xml")
