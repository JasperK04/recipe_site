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
    app.run(debug=True, host='0.0.0.0', port=5000)
