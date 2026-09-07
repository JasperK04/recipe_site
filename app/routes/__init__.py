"""Routes package for the Recipe application.

This module imports and exposes all route blueprints.
"""

from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.main import main_bp
from app.routes.recipes import recipe_overview_bp, recipes_bp

__all__ = ["admin_bp", "auth_bp", "main_bp", "recipe_overview_bp", "recipes_bp"]
