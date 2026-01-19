# Recipe Site

A Flask web application for managing and sharing cooking recipes. Save, organize, and discover delicious recipes with an easy-to-use interface.

## Features

- 🔐 User authentication (register, login, logout)
- 📝 Add, view, edit, and delete recipes
- 🔍 Search recipes by title or description
- 🏷️ Filter recipes by category
- ⏱️ Track prep time, cook time, and servings
- 👤 Personal recipe collection
- 📱 Responsive design with Bootstrap 5

## Technology Stack

- **Flask** - Web framework
- **Flask-Login** - User session management
- **Flask-Session** - Server-side session storage
- **Flask-SQLAlchemy** - Database ORM
- **Flask-WTF** - Form handling and validation
- **SQLite** - Database (default, can be changed to PostgreSQL, MySQL, etc.)
- **Bootstrap 5** - Frontend UI framework

## Project Structure

```
recepy_site/
├── app/
│   ├── __init__.py          # Application factory
│   ├── models.py            # Database models (User, Recipe)
│   ├── forms.py             # WTForms for validation
│   ├── auth.py              # Authentication routes
│   ├── recipes.py           # Recipe management routes
│   ├── main.py              # Main routes (home, about)
│   ├── templates/           # Jinja2 templates
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── about.html
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   └── recipes/
│   │       ├── list.html
│   │       ├── view.html
│   │       ├── form.html
│   │       └── my_recipes.html
│   └── static/              # Static files (CSS, JS)
│       ├── css/
│       └── js/
├── config.py                # Configuration settings
├── run.py                   # Application entry point
├── requirements.txt         # Python dependencies
├── .env.example            # Example environment variables
└── README.md               # This file
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/JasperK04/recepy_site.git
   cd recepy_site
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and update the following:
   - `SECRET_KEY`: Generate a secure secret key
   - `DATABASE_URL`: (Optional) Use PostgreSQL or MySQL instead of SQLite

5. **Initialize the database**
   ```bash
   python run.py
   ```
   The application will automatically create the SQLite database on first run.

## Usage

### Running the Application

```bash
python run.py
```

The application will be available at `http://localhost:5000`

### Using Flask CLI

You can also use Flask's built-in development server:

```bash
export FLASK_APP=run.py
export FLASK_ENV=development
flask run
```

### Database Management

Access the Flask shell to interact with the database:

```bash
flask shell
```

Example commands in the shell:
```python
# Create a new user
user = User(username='testuser', email='test@example.com')
user.set_password('password123')
db.session.add(user)
db.session.commit()

# Query recipes
recipes = Recipe.query.all()
```

## Development

### Adding New Features

1. Database models: Edit `app/models.py`
2. Forms: Edit `app/forms.py`
3. Routes: Edit appropriate blueprint in `app/` directory
4. Templates: Add/edit files in `app/templates/`
5. Static files: Add files to `app/static/`

### Database Migrations (Optional)

For production use, consider using Flask-Migrate for database migrations:

```bash
pip install Flask-Migrate
```

## Deployment

### Production Configuration

1. Set `FLASK_ENV=production` in your `.env` file
2. Use a strong `SECRET_KEY`
3. Configure a production database (PostgreSQL recommended)
4. Use a production WSGI server like Gunicorn:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:8000 run:app
   ```

### Security Notes

- Never commit `.env` file to version control
- Use strong passwords for user accounts
- Enable HTTPS in production
- Set secure session cookies
- Regularly update dependencies

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available for personal use.

## Author

Created by JasperK04

## Support

For issues or questions, please open an issue on GitHub.
