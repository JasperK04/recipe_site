from datetime import UTC, datetime

from flask import Flask, flash, jsonify, redirect, request, url_for
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf

from config import config
from flask_session import Session

db = SQLAlchemy()
login_manager = LoginManager()
session = Session()
migrate = Migrate()

from app.api import api_bp
from app.navigation import (
    back_url,
    load_pending_back_url,
    remember_back_url_for_login,
)
from app.routes import admin_bp, auth_bp, main_bp, recipe_overview_bp, recipes_bp


def create_app(config_name="default"):
    """Application factory pattern."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    session.init_app(app)
    migrate.init_app(app, db)
    # CSRF protection for forms and manual tokens
    csrf = CSRFProtect()
    csrf.init_app(app)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        """Return JSON for AJAX forms instead of Flask-WTF's HTML error page."""
        if (
            request.path.startswith("/api/")
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        ):
            return jsonify(
                {
                    "status": "error",
                    "message": "Je formulier is verlopen. Vernieuw de pagina en probeer opnieuw.",
                }
            ), 400
        return error.description, 400

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
        def recipe_url(recipe, *, external=False):
            return url_for(
                "recipes.view_recipe",
                recipe_id=recipe.id,
                title=recipe.url_title,
                _external=external,
            )

        return {"recipe_url": recipe_url, "back_url": back_url}

    # Register CLI commands
    from app.cli import register_commands

    register_commands(app)

    @app.before_request
    def navigation_and_account_checks():
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
