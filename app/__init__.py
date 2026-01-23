from datetime import datetime

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf

from config import config
from flask_session import Session

db = SQLAlchemy()
login_manager = LoginManager()
session = Session()
migrate = Migrate()


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
    from app.routes import auth_bp, main_bp, recipes_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(recipes_bp, url_prefix="/recipes")

    # Register CLI commands
    from app.cli import register_commands

    register_commands(app)

    # expose csrf_token() in templates for manual forms
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf)

    # Inject current year for footer
    @app.context_processor
    def inject_year():
        return dict(current_year=datetime.now().year)

    return app
