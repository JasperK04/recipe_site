"""
Recipe Site - Flask Application Entry Point

A Flask application for managing cooking recipes.
"""

import os

from app import create_app, db
from app.models import Recipe, User
from utils import is_running_flask_db_command, sqlite_path_from_uri

# Create the Flask application
app = create_app(os.environ.get("FLASK_ENV", "development"))

# Ensure tables exist only on first startup of a brand-new SQLite database.
if not is_running_flask_db_command():
    with app.app_context():
        try:
            db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
            sqlite_db_file = sqlite_path_from_uri(db_uri)
            if sqlite_db_file and not os.path.exists(sqlite_db_file):
                db.create_all()
        except Exception as e:
            app.logger.warning("Failed to ensure database tables: %s", e)


@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell."""
    return {"db": db, "User": User, "Recipe": Recipe}


if __name__ == "__main__":
    # Get debug mode from configuration, not hardcoded
    debug_mode = app.config.get("DEBUG", False)
    # For development, bind to localhost only for security
    host = "0.0.0.0" if debug_mode else "127.0.0.1"
    app.run(debug=debug_mode, host=host, port=5000)
