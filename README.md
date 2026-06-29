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
- **Flask-Migrate** - Database migrations
- **SQLite** - Database (default, can be changed to PostgreSQL, MySQL, etc.)
- **Bootstrap 5** - Frontend UI framework
- **Faker** - Mock data generation for testing

## Project Structure

```
recipe_site/
├── app/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── main.py
│   │   └── recipes.py
│   ├── models.py
│   ├── forms.py
│   ├── templates/
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
│   └── static/
│       ├── css/
│       └── js/
├── config.py
├── run.py
├── pyproject.toml
├── .env.example
└── README.md
```

## Installation

### Prerequisites

- Python 3.12 or higher
- uv (Python package installer)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/JasperK04/recipe_site.git
   cd recipe_site
   ```

2. **Create a virtual environment**
   ```bash
   uv sync
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and update the following:
   - `SECRET_KEY`: Generate a secure secret key
   - `OPENAI_API_KEY`: Required by the app configuration
   - `DATABASE_URL`: (Optional)
   - `CREATOR_REQUEST_NOTIFICATION_EMAIL`: Where creator requests are sent
   - `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`: SMTP settings for notifications
   - If SMTP settings are omitted, creator requests still work but no email is sent

4. **Initialize the database**
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

#### Database Migrations

This project uses Flask-Migrate for database schema migrations. Here's how to use it:

**Initialize migrations** (only needed once, already done):
```bash
flask db init
```

**Create a new migration** after changing models:
```bash
flask db migrate -m "Description of changes"
```

**Apply migrations** to the database:
```bash
flask db upgrade
```

**Rollback a migration**:
```bash
flask db downgrade
```

#### CLI Commands

The application provides several CLI commands for database and user management:

**Create a new user:**
```bash
flask create-user <username> <email>
# You'll be prompted for password
```

**Create an admin user:**
```bash
flask create-admin <username> <email>
# You'll be prompted for password
```

**Populate database with mock data:**
```bash
# Create 5 users and 20 recipes (default)
flask seed-data

# Create custom amounts
flask seed-data --users 10 --recipes 50
```
*Note: Seeded users have default password: `password123`*

**Display database statistics:**
```bash
flask db-stats
```

**Clear all data from database:**
```bash
flask clear-data
# You'll be asked to confirm
```

#### Interactive Shell

Access the Flask shell to interact with the database directly:

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

## Deployment

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
