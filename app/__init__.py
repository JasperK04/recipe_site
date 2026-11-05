from datetime import UTC, datetime

from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf
from werkzeug.exceptions import HTTPException

from config import config
from flask_session import Session

from app.errors import error_page_context

db = SQLAlchemy()
login_manager = LoginManager()
session = Session()
migrate = Migrate()

from app.api import api_bp
from app.navigation import (
    RECIPE_CATEGORIES,
    back_url,
    load_pending_back_url,
    remember_back_url_for_login,
)
from app.routes import admin_bp, auth_bp, main_bp, recipe_overview_bp, recipes_bp
from app.services.analytics import CONSENT_COOKIE, VISITOR_COOKIE, Analytics


def create_app(config_name="default"):
    """Application factory pattern."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    app.config.setdefault("ANALYTICS_SLOW_REQUEST_MS", 1000)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    session.init_app(app)
    migrate.init_app(app, db)
    # CSRF protection for forms and manual tokens
    csrf = CSRFProtect()
    csrf.init_app(app)

    def wants_json_response():
        return (
            request.path.startswith("/api/")
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.accept_mimetypes.best == "application/json"
        )

    def render_error(error, *, status_code, message=None):
        if wants_json_response():
            return jsonify(
                {
                    "status": "error",
                    "message": message or "Er is iets misgegaan. Probeer het opnieuw.",
                }
            ), status_code
        return (
            render_template(
                "errors/error.html",
                **error_page_context(
                    status_code,
                    message or "Er is iets misgegaan. Probeer het opnieuw.",
                ),
            ),
            status_code,
        )

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        Analytics.error(error)
        return render_error(
            error,
            status_code=400,
            message="Je formulier is verlopen. Vernieuw de pagina en probeer opnieuw.",
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        expected_temporary_image_miss = (
            request.endpoint == "recipes.pending_recipe_image" and error.code == 404
        )
        if error.code != 500 and not expected_temporary_image_miss:
            Analytics.error(error)
        if expected_temporary_image_miss:
            return error
        return render_error(error, status_code=error.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled application error")
        Analytics.error(error)
        return render_error(error, status_code=500)

    # Configure login
    login_manager.login_view = "auth.login"  # type: ignore
    login_manager.login_message = "Please log in to access this page."

    @login_manager.unauthorized_handler
    def redirect_to_login():
        """Preserve the protected URL and its preceding page during login."""
        remember_back_url_for_login()
        if login_manager.login_message:
            flash(login_manager.login_message, login_manager.login_message_category)
        destination = request.full_path if request.query_string else request.path
        return redirect(url_for("auth.login", next=destination))

    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(auth_bp, url_prefix="/account")
    app.register_blueprint(recipe_overview_bp, url_prefix="/recepten")
    app.register_blueprint(recipes_bp, url_prefix="/recept")

    @app.context_processor
    def inject_recipe_url():
        from app.seo import recipe_description

        def recipe_url(recipe, *, external=False):
            return url_for(
                "recipes.view_recipe",
                recipe_id=recipe.id,
                title=recipe.url_title,
                _external=external,
            )

        return {
            "recipe_url": recipe_url,
            "recipe_categories": RECIPE_CATEGORIES,
            "back_url": back_url,
            "recipe_description": recipe_description,
        }

    # Register CLI commands
    from app.cli import register_commands

    register_commands(app)

    @app.before_request
    def navigation_and_account_checks():
        g.analytics_started_at = datetime.now(UTC)
        load_pending_back_url()
        # Deactivated accounts are logged out immediately, including existing sessions.
        if current_user.is_authenticated and not current_user.is_active:
            logout_user()
            flash(
                "Je account is gedeactiveerd. Neem contact op met een beheerder.",
                "warning",
            )
            if request.endpoint == "auth.login":
                return None
            return redirect(url_for("auth.login"))

    @app.after_request
    def record_analytics(response):
        Analytics.record_request(response)
        visitor_cookie = getattr(g, "analytics_set_visitor_cookie", None)
        if visitor_cookie:
            response.set_cookie(
                VISITOR_COOKIE,
                visitor_cookie,
                max_age=395 * 24 * 60 * 60,
                httponly=True,
                samesite="Lax",
                secure=request.is_secure,
            )
        if request.endpoint == "main.cookie_consent" and request.method == "POST":
            choice = request.get_json(silent=True) or {}
            consent = "analytics" if choice.get("analytics") is True else "essential"
            response.set_cookie(
                CONSENT_COOKIE,
                consent,
                max_age=180 * 24 * 60 * 60,
                httponly=True,
                samesite="Lax",
                secure=request.is_secure,
            )
            if consent != "analytics":
                response.delete_cookie(VISITOR_COOKIE, samesite="Lax", secure=request.is_secure)
        elif request.cookies.get(CONSENT_COOKIE) != "analytics":
            # Also clean up identifiers created by an older version of the site
            # while the visitor is undecided or has declined.
            response.delete_cookie(VISITOR_COOKIE, samesite="Lax", secure=request.is_secure)
        return response

    # expose csrf_token() in templates for manual forms
    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": generate_csrf}

    # Inject current year for footer
    @app.context_processor
    def inject_year():
        return {"current_year": datetime.now(UTC).year}

    @app.context_processor
    def inject_pending_creator_requests():
        from flask_login import current_user as flask_current_user

        from app.api.recipes import pending_recipe_moderation_count
        from app.api.users import pending_creator_request_count

        pending_creator_requests = 0
        pending_recipe_moderation = 0
        if flask_current_user.is_authenticated and flask_current_user.is_admin:
            pending_creator_requests = pending_creator_request_count()
            pending_recipe_moderation = pending_recipe_moderation_count()

        return {
            "pending_creator_requests": pending_creator_requests,
            "pending_recipe_moderation": pending_recipe_moderation,
        }

    return app
