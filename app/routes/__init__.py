"""Routes package for the Recipe application.

This module imports and exposes all route blueprints.
"""

from app.routes.auth import auth_bp
from app.routes.main import main_bp
from app.routes.recipes import recipes_bp

__all__ = ["main_bp", "auth_bp", "recipes_bp"]
