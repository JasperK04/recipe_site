"""
CLI commands for the Recipe application.

This module provides Flask CLI commands for database operations, user management,
and generating mock data.
"""

import click
from faker import Faker
from flask import Flask

from app import db
from app.models import Recipe, User

fake = Faker("nl_NL")


def register_commands(app: Flask):
    """Register all CLI commands with the Flask application."""

    @app.cli.command("create-user")
    @click.argument("username")
    @click.argument("email")
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Password for the user",
    )
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
            click.echo(
                click.style(
                    f'Fout: Gebruiker met gebruikersnaam "{username}" of e-mail "{email}" bestaat al.',
                    fg="red",
                )
            )
            return

        # Create new user
        user = User(username=username, email=email)  # type: ignore
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        click.echo(
            click.style(f"✓ Gebruiker aangemaakt: {username} ({email})", fg="green")
        )

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.argument("email")
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Password for the admin user",
    )
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
            click.echo(
                click.style(
                    f'Fout: Gebruiker met gebruikersnaam "{username}" of e-mail "{email}" bestaat al.',
                    fg="red",
                )
            )
            return

        # Create new admin user
        user = User(username=username, email=email)  # type: ignore
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        click.echo(
            click.style(
                f"✓ Admin-gebruiker aangemaakt: {username} ({email})", fg="green"
            )
        )

    @app.cli.command("seed-data")
    @click.option("--users", default=5, help="Number of users to create (default: 5)")
    @click.option(
        "--recipes", default=40, help="Number of recipes to create (default: 40)"
    )
    def seed_data(users, recipes):
        """Populate database with mock data using Faker.

        Usage:
            flask seed-data
            flask seed-data --users 10 --recipes 50
        """
        num_recipes = Recipe.query.delete()  # noqa: F841
        num_users = User.query.delete()  # noqa: F841
        db.session.commit()

        # Create mock users
        created_users = []
        click.echo(f"\nMaak {users} gebruikers aan...")

        for i in range(users):
            username = fake.user_name()
            # Generate proper email address
            email = fake.email()

            # Ensure unique username and email
            counter = 1
            original_username = username
            while User.query.filter(
                (User.username == username) | (User.email == email)
            ).first():
                username = f"{original_username}{counter}"
                email = fake.email()
                counter += 1

            user = User(username=username, email=email)  # type: ignore
            user.set_password("password123")  # Default password for seeded users
            db.session.add(user)
            created_users.append(user)

        admin = User(username="admin", email="admin@example.com")  # type: ignore
        admin.set_password("admin123")
        db.session.add(admin)
        created_users.append(admin)

        db.session.commit()

        categories = [
            "voorgerecht",
            "ontbijt",
            "lunch",
            "hoofdgerecht",
            "nagerecht",
            "snack",
            "drank",
        ]

        click.echo(f"\nMaak {recipes} recepten aan...")
        for i in range(recipes):
            # create structured ingredients (list of dicts)
            ing_count = fake.random_int(min=3, max=8)
            ingredient_list = []
            measurements = ["g", "kg", "ml", "l", "el", "tl", "stuks"]
            for _ in range(ing_count):
                name = fake.word()
                qty = round(fake.random.uniform(0.5, 500), 2)
                measurement = fake.random_element(elements=measurements)
                ingredient_list.append(
                    {"name_": name, "quantity": qty, "measurement": measurement}
                )

            # instructions as list of steps
            step_count = fake.random_int(min=2, max=5)
            instruction_list = [fake.sentence() for _ in range(step_count)]

            recipe = Recipe(
                title=fake.catch_phrase(),  # type: ignore
                description=fake.text(max_nb_chars=200),  # type: ignore
                ingredients=ingredient_list,  # type: ignore
                instructions=instruction_list,  # type: ignore
                prep_time=fake.random_int(min=5, max=60),  # type: ignore
                cook_time=fake.random_int(min=10, max=120),  # type: ignore
                servings=fake.random_int(min=1, max=8),  # type: ignore
                category=fake.random_element(elements=categories),  # type: ignore
                user_id=fake.random_element(elements=created_users).id,  # type: ignore
            )
            db.session.add(recipe)

        db.session.commit()

    @app.cli.command("clear-data")
    def clear_data():
        """Delete all data from the database.

        Usage:
            flask clear-data
        """
        click.echo("Alle data uit de database verwijderen...")

        # Delete all recipes
        num_recipes = Recipe.query.delete()  # noqa: F841
        # Delete all users
        num_users = User.query.delete()  # noqa: F841

        db.session.commit()

    @app.cli.command("db-stats")
    def db_stats():
        """Display database statistics.

        Usage:
            flask db-stats
        """
        num_users = User.query.count()
        num_recipes = Recipe.query.count()

        click.echo(click.style("\n=== Database Statistieken ===", fg="cyan", bold=True))
        click.echo(f"Gebruikers:   {num_users}")
        click.echo(f"Recepten: {num_recipes}")

        if num_users > 0:
            click.echo(
                click.style("\n=== Top Recipe Authors ===", fg="cyan", bold=True)
            )
            # Get users with most recipes (only users who have at least one recipe)
            users_with_counts = (
                db.session.query(
                    User.username, db.func.count(Recipe.id).label("recipe_count")
                )
                .join(Recipe)
                .group_by(User.id)
                .order_by(db.func.count(Recipe.id).desc())
                .limit(5)
                .all()
            )

            if users_with_counts:
                for username, count in users_with_counts:
                    click.echo(f"{username}: {count} recept(en)")
            else:
                click.echo("Nog geen recepten aangemaakt.")
