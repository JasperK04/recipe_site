"""
CLI commands for the Recipe application.

This module provides Flask CLI commands for database operations, user management,
and generating mock data.
"""

import os
import random
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import click
from faker import Faker
from flask import Flask

from app import db
from app.models import (
    Recipe,
    User,
)
from app.recipe_generator import generate_recipes
from config import BASE_DIR
from utils import (
    clear_directory_files,
    create_zip_from_directory,
    ensure_directory,
    restore_directory_from_zip,
    sqlite_path_from_uri,
)

fake = Faker("nl_NL")


def _get_db_file_from_uri(uri: str) -> str:
    """Convert a SQLite SQLALCHEMY_DATABASE_URI to a file system path."""
    db_path = sqlite_path_from_uri(uri)
    if db_path is None:
        raise ValueError(
            "Only sqlite:/// database URIs are supported for backup/restore"
        )
    return db_path


def _get_recipe_image_dir(app: Flask) -> Path:
    return ensure_directory(app.config["RECIPE_IMAGE_DIR"])


def _clear_recipe_images(app: Flask) -> int:
    return clear_directory_files(_get_recipe_image_dir(app), pattern="*.webp")


def _create_recipe_backup_zip(app: Flask, backup_zip_path: Path) -> int:
    return create_zip_from_directory(
        _get_recipe_image_dir(app),
        backup_zip_path,
        archive_root="recipe",
        pattern="*.webp",
    )


def _restore_recipe_from_backup_zip(app: Flask, backup_zip_path: Path) -> int:
    return restore_directory_from_zip(
        backup_zip_path,
        _get_recipe_image_dir(app),
        pattern="*.webp",
    )


def _clear_filesystem_sessions(app: Flask) -> int:
    """Remove all persisted Flask-Session files and return deleted file count."""
    if app.config.get("SESSION_TYPE") != "filesystem":
        return 0

    session_dir = app.config.get("SESSION_FILE_DIR")
    if not session_dir:
        session_dir = os.path.join(os.getcwd(), "flask_session")

    if not os.path.isdir(session_dir):
        return 0

    return clear_directory_files(session_dir, pattern="*")


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
        user = User(username=username, email=email, role=User.ROLE_FIJNPROEVER)  # type: ignore
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
        user = User(username=username, email=email, role=User.ROLE_CHEF_DE_CUISINE)  # type: ignore
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        click.echo(
            click.style(
                f"✓ Admin-gebruiker aangemaakt: {username} ({email})", fg="green"
            )
        )

    @app.cli.command("seed-data")
    @click.option("--users", default=10, help="Number of users to create (default: 10)")
    @click.option(
        "--recipes", default=100, help="Number of recipes to create (default: 100)"
    )
    def seed_data(users, recipes):
        """Populate database with mock data using Faker.

        Usage:
            flask seed-data
            flask seed-data --users 10 --recipes 50
        """
        # Clear association tables first to avoid unique-constraint leftovers

        Recipe.query.delete()  # noqa: F841
        _clear_recipe_images(app)
        User.query.delete()  # noqa: F841
        db.session.commit()

        # Create mock users
        created_users = []
        click.echo(f"\nMaak {users} gebruikers aan...")

        for i in range(users):
            username = fake.user_name()
            email = fake.email()

            counter = 1
            original_username = username
            while User.query.filter(
                (User.username == username) | (User.email == email)
            ).first():
                username = f"{original_username}{counter}"
                email = fake.email()
                counter += 1

            user = User(username=username, email=email, role=User.ROLE_FIJNPROEVER)  # type: ignore
            user.set_password("password123")
            db.session.add(user)
            created_users.append(user)

        admin_username = os.getenv("admin_username", "admin")
        admin_email = os.getenv("admin_email", "admin@example.com")
        admin_password = os.getenv("admin_password", "admin123")

        admin = User(username=admin_username, email=admin_email, role=User.ROLE_CHEF_DE_CUISINE)  # type: ignore
        admin.set_password(admin_password)
        db.session.add(admin)
        created_users.append(admin)

        db.session.commit()

        reviewers = [
            user
            for user in created_users
            if user.role == User.ROLE_FIJNPROEVER and user.username != admin_username
        ]
        creator_count = min(len(reviewers), max(1, users // 4))
        for creator in random.sample(reviewers, k=creator_count) if reviewers else []:
            creator.role = User.ROLE_LEERLING_KOK

        db.session.commit()

        click.echo(f"\nMaak {recipes} recepten aan ...")
        generated = generate_recipes(n=recipes)
        measurements = ["g", "kg", "ml", "l", "el", "tl", "stuks"]

        for rec in generated:
            ingredient_list = []
            for name in rec.get("ingredients", []):
                qty = round(fake.random.uniform(1, 500), 2)
                measurement = random.choice(measurements)
                ingredient_list.append(
                    {"name": name, "quantity": qty, "measurement": measurement}
                )

            step_count = fake.random_int(min=2, max=5)
            instruction_list = [fake.sentence() for _ in range(step_count)]

            recipe = Recipe(
                title=rec.get("title"),
                description=fake.text(max_nb_chars=200),
                ingredients=ingredient_list,
                instructions=instruction_list,
                prep_time=fake.random_int(min=5, max=60),
                cook_time=fake.random_int(min=10, max=120),
                servings=fake.random_int(min=1, max=8),
                category=rec.get("category", ""),
                user_id=random.choice(
                    [
                        u
                        for u in created_users
                        if u.role >= User.ROLE_LEERLING_KOK
                    ]
                ).id,
            )

            r = random.random()
            if r < 0.70:
                recipe.status = "public"
            elif r < 0.85:
                recipe.status = "draft"
            else:
                recipe.status = "deactivated"

            db.session.add(recipe)

        db.session.commit()

        # Add favorites for created users
        try:
            all_recipes = Recipe.query.all()
            if all_recipes:
                for user in created_users:
                    fav_count = random.randint(0, min(6, len(all_recipes)))
                    if fav_count == 0:
                        continue
                    favorites = random.sample(all_recipes, k=fav_count)
                    for r in favorites:
                        if not user.favorites.filter_by(id=r.id).first():
                            user.favorites.append(r)
                db.session.commit()
        except Exception:
            db.session.rollback()

    @app.cli.command("clear-data")
    def clear_data():
        """Delete all data from the database.

        Usage:
            flask clear-data
        """
        click.echo("Alle data uit de database verwijderen...")

        Recipe.query.delete()  # noqa: F841
        deleted_images = _clear_recipe_images(app)
        User.query.delete()  # noqa: F841

        db.session.commit()
        click.echo(f"Verwijderde recepten-afbeeldingen: {deleted_images}")

    @app.cli.command("db-stats")
    def db_stats():
        """Display database statistics.

        Usage:
            flask db-stats
        """
        num_users = User.query.count()
        num_active_users = User.query.filter_by(is_active=True).count()
        num_deactivated_users = User.query.filter_by(is_active=False).count()
        num_reviewers = User.query.filter_by(role=User.ROLE_FIJNPROEVER).count()
        num_creators = 0
        for role in [
            User.ROLE_LEERLING_KOK,
            User.ROLE_ZELFSTANDIG_KOK,
            User.ROLE_CHEF_DE_PARTIE,
            User.ROLE_SOUS_CHEF,
        ]:
            num_creators += User.query.filter_by(role=role).count()
        num_admins = User.query.filter_by(role=User.ROLE_CHEF_DE_CUISINE).count()
        num_recipes = Recipe.query.count()

        click.echo(click.style("\n=== Database Statistieken ===", fg="cyan", bold=True))
        click.echo(f"Gebruikers:         {num_users}")
        click.echo(f"  - Actief:         {num_active_users}")
        click.echo(f"  - Gedeactiveerd:  {num_deactivated_users}")
        click.echo(f"  - Reviewers:      {num_reviewers}")
        click.echo(f"  - Creators:       {num_creators}")
        click.echo(f"  - Admins:         {num_admins}")
        click.echo(f"Recepten:           {num_recipes}")

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

    @app.cli.command("backup")
    def backup_database():
        """Create backups for database (backup.db) and images (backup.zip)."""
        db_uri = app.config["SQLALCHEMY_DATABASE_URI"]

        db_path = _get_db_file_from_uri(db_uri)
        if not os.path.exists(db_path):
            raise click.ClickException(f"Database file not found: {db_path}")

        backup_db_path = Path(os.path.dirname(db_path) or ".") / "backup.db"
        shutil.copy2(db_path, backup_db_path)
        backup_zip_path = _get_recipe_image_dir(app).parent / "backup.zip"
        _create_recipe_backup_zip(app, backup_zip_path)

        now = datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%d-%m-%Y %H:%M:%S")
        rel_db = os.path.relpath(db_path, start=BASE_DIR)
        rel_backup_db = os.path.relpath(backup_db_path, start=BASE_DIR)
        rel_backup_zip = os.path.relpath(backup_zip_path, start=BASE_DIR)
        print(
            f"Backup completed ({now}):\n\t{rel_db:15}\t-> {rel_backup_db}\n\t{'data/recipe/':15}\t-> {rel_backup_zip}."
        )

    @app.cli.command("restore")
    def restore_database():
        db_uri = app.config["SQLALCHEMY_DATABASE_URI"]

        db_path = _get_db_file_from_uri(db_uri)
        backup_db_path = Path(os.path.dirname(db_path) or ".") / "backup.db"
        backup_zip_path = _get_recipe_image_dir(app).parent / "backup.zip"

        if not backup_db_path.exists():
            raise click.ClickException(f"Backup file not found: {backup_db_path}")
        if not backup_zip_path.exists():
            raise click.ClickException(f"Image backup not found: {backup_zip_path}")

        db.session.remove()
        db.engine.dispose()

        shutil.copy2(backup_db_path, db_path)
        _restore_recipe_from_backup_zip(app, backup_zip_path)

        db.engine.dispose()
        _clear_filesystem_sessions(app)

        now = datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%d-%m-%Y %H:%M:%S")
        rel_db = os.path.relpath(db_path, start=BASE_DIR)
        rel_backup_db = os.path.relpath(backup_db_path, start=BASE_DIR)
        rel_backup_zip = os.path.relpath(backup_zip_path, start=BASE_DIR)
        print(
            f"Restore completed ({now}):\n\t{rel_backup_db:15}\t-> {rel_db}\n\t{rel_backup_zip:15}\t-> data/recipe/"
        )
