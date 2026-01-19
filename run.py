"""
Recipe Site - Flask Application Entry Point

A Flask application for managing cooking recipes.
"""
import os
from dotenv import load_dotenv
from app import create_app, db
from app.models import User, Recipe

# Load environment variables
load_dotenv()

# Create the Flask application
app = create_app(os.environ.get('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell."""
    return {'db': db, 'User': User, 'Recipe': Recipe}


if __name__ == '__main__':

    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print('Warning: failed to ensure database tables:', e)

    # Get debug mode from configuration, not hardcoded
    debug_mode = app.config.get('DEBUG', False)
    # For development, bind to localhost only for security
    host = '0.0.0.0' if debug_mode else '127.0.0.1'
    app.run(debug=debug_mode, host=host, port=5000)
