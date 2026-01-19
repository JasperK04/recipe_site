"""
CLI commands for the Recipe application.

This module provides Flask CLI commands for database operations, user management,
and generating mock data.
"""
import click
from flask import Flask
from faker import Faker
from app import db
from app.models import User, Recipe


fake = Faker()


def register_commands(app: Flask):
    """Register all CLI commands with the Flask application."""
    
    @app.cli.command('create-user')
    @click.argument('username')
    @click.argument('email')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True,
                  help='Password for the user')
    def create_user(username, email, password):
        """Create a new user account.
        
        Usage:
            flask create-user <username> <email>
        """
        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            click.echo(click.style(f'Error: User with username "{username}" or email "{email}" already exists.', fg='red'))
            return
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        click.echo(click.style(f'✓ Successfully created user: {username} ({email})', fg='green'))
    
    @app.cli.command('create-admin')
    @click.argument('username')
    @click.argument('email')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True,
                  help='Password for the admin user')
    def create_admin(username, email, password):
        """Create a new admin user account.
        
        Usage:
            flask create-admin <username> <email>
        """
        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            click.echo(click.style(f'Error: User with username "{username}" or email "{email}" already exists.', fg='red'))
            return
        
        # Create new admin user
        user = User(username=username, email=email)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        click.echo(click.style(f'✓ Successfully created admin user: {username} ({email})', fg='green'))
    
    @app.cli.command('seed-data')
    @click.option('--users', default=5, help='Number of users to create (default: 5)')
    @click.option('--recipes', default=20, help='Number of recipes to create (default: 20)')
    def seed_data(users, recipes):
        """Populate database with mock data using Faker.
        
        Usage:
            flask seed-data
            flask seed-data --users 10 --recipes 50
        """
        click.echo(click.style('Seeding database with mock data...', fg='cyan'))
        
        # Create mock users
        created_users = []
        click.echo(f'\nCreating {users} users...')
        
        for i in range(users):
            username = fake.user_name()
            # Generate proper email address
            email = fake.email()
            
            # Ensure unique username and email
            counter = 1
            original_username = username
            while User.query.filter((User.username == username) | (User.email == email)).first():
                username = f"{original_username}{counter}"
                email = fake.email()
                counter += 1
            
            user = User(username=username, email=email)
            user.set_password('password123')  # Default password for seeded users
            db.session.add(user)
            created_users.append(user)
            click.echo(f'  ✓ Created user: {username}')
        
        db.session.commit()
        
        # Create mock recipes
        click.echo(f'\nCreating {recipes} recipes...')
        
        categories = ['appetizer', 'breakfast', 'lunch', 'dinner', 'dessert', 'snack', 'beverage']
        
        for i in range(recipes):
            recipe = Recipe(
                title=fake.catch_phrase(),
                description=fake.text(max_nb_chars=200),
                ingredients='\n'.join([f"{fake.word()} - {fake.random_int(min=1, max=5)} {fake.word()}" for _ in range(fake.random_int(min=3, max=8))]),
                instructions='\n'.join([f"{j+1}. {fake.sentence()}" for j in range(fake.random_int(min=3, max=8))]),
                prep_time=fake.random_int(min=5, max=60),
                cook_time=fake.random_int(min=10, max=120),
                servings=fake.random_int(min=1, max=12),
                category=fake.random_element(elements=categories),
                user_id=fake.random_element(elements=created_users).id
            )
            db.session.add(recipe)
            click.echo(f'  ✓ Created recipe: {recipe.title}')
        
        db.session.commit()
        
        click.echo(click.style(f'\n✓ Successfully seeded database with {users} users and {recipes} recipes!', fg='green'))
        click.echo(click.style('  Default password for all seeded users: password123', fg='yellow'))
    
    @app.cli.command('clear-data')
    @click.confirmation_option(prompt='Are you sure you want to delete all data?')
    def clear_data():
        """Delete all data from the database.
        
        Usage:
            flask clear-data
        """
        click.echo(click.style('Clearing all data from database...', fg='yellow'))
        
        # Delete all recipes
        num_recipes = Recipe.query.delete()
        # Delete all users
        num_users = User.query.delete()
        
        db.session.commit()
        
        click.echo(click.style(f'✓ Deleted {num_recipes} recipes and {num_users} users', fg='green'))
    
    @app.cli.command('db-stats')
    def db_stats():
        """Display database statistics.
        
        Usage:
            flask db-stats
        """
        num_users = User.query.count()
        num_recipes = Recipe.query.count()
        
        click.echo(click.style('\n=== Database Statistics ===', fg='cyan', bold=True))
        click.echo(f'Users:   {num_users}')
        click.echo(f'Recipes: {num_recipes}')
        
        if num_users > 0:
            click.echo(click.style('\n=== Top Recipe Authors ===', fg='cyan', bold=True))
            # Get users with most recipes (only users who have at least one recipe)
            users_with_counts = db.session.query(
                User.username, 
                db.func.count(Recipe.id).label('recipe_count')
            ).join(Recipe).group_by(User.id).order_by(
                db.func.count(Recipe.id).desc()
            ).limit(5).all()
            
            if users_with_counts:
                for username, count in users_with_counts:
                    click.echo(f'{username}: {count} recipe(s)')
            else:
                click.echo('No recipes created yet.')
