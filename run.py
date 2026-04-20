"""
Recipe Site - Flask Application Entry Point

A Flask application for managing cooking recipes.
"""

import os
import sys

from app import create_app, db
from app.models import KitchenMachine, Recipe, User

# Create the Flask application
app = create_app(os.environ.get("FLASK_ENV", "development"))

def _running_flask_db_command() -> bool:
    argv = [arg.lower() for arg in sys.argv[1:4]]
    return "db" in argv


# Ensure tables exist for direct app startup, but skip while running Alembic commands.
if not _running_flask_db_command():
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning("Failed to ensure database tables: %s", e)


@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell."""
    return {"db": db, "User": User, "Recipe": Recipe, "KitchenMachine": KitchenMachine}


if __name__ == "__main__":
    # Get debug mode from configuration, not hardcoded
    debug_mode = app.config.get("DEBUG", False)
    # For development, bind to localhost only for security
    host = "0.0.0.0" if debug_mode else "127.0.0.1"
    app.run(debug=debug_mode, host=host, port=5000)
