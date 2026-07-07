from datetime import datetime

from flask import Flask, flash, redirect, request, url_for
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf

from config import config
from flask_session import Session

db = SQLAlchemy()
login_manager = LoginManager()
session = Session()
migrate = Migrate()

from app.api import api_bp  # noqa: E402
from app.routes import admin_bp, auth_bp, main_bp, recipes_bp  # noqa: E402


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

    # Configure login
    login_manager.login_view = "auth.login"  # type: ignore
    login_manager.login_message = "Please log in to access this page."

    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(recipes_bp, url_prefix="/recipes")

    # Register CLI commands
    from app.cli import register_commands

    register_commands(app)

    @app.before_request
    def enforce_active_account():
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
        return dict(csrf_token=generate_csrf)

    # Inject current year for footer
    @app.context_processor
    def inject_year():
        return dict(current_year=datetime.now().year)

    @app.context_processor
    def inject_pending_creator_requests():
        from flask_login import current_user as flask_current_user

        from app.api.users import pending_creator_request_count
        from app.api.recipes import pending_recipe_moderation_count

        pending_creator_requests = 0
        pending_recipe_moderation = 0
        if flask_current_user.is_authenticated and flask_current_user.is_admin:
            pending_creator_requests = pending_creator_request_count()
            pending_recipe_moderation = pending_recipe_moderation_count()

        return dict(
            pending_creator_requests=pending_creator_requests,
            pending_recipe_moderation=pending_recipe_moderation,
        )

    return app
