"""
CLI commands for the Recipe application.

This module provides Flask CLI commands for database operations, user management,
and generating mock data.
"""

import os
import random
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

import click
from faker import Faker
from flask import Flask

from app import db
from app.models import (
    KitchenMachine,
    Recipe,
    User,
    recipe_machines,
)
from app.recipe_generator import generate_recipes
from config import BASE_DIR, config

fake = Faker("nl_NL")


def _get_db_file_from_uri(uri: str) -> str:
    """Convert a SQLite SQLALCHEMY_DATABASE_URI to a file system path."""

    # Absolute path: sqlite:////absolute/path.db
    if uri.startswith("sqlite:////"):
        return "/" + uri[len("sqlite:////") :]

    # Relative path: sqlite:///relative/path.db
    if uri.startswith("sqlite:///"):
        return uri[len("sqlite:///") :]


def _clear_filesystem_sessions(app: Flask) -> int:
    """Remove all persisted Flask-Session files and return deleted file count."""
    if app.config.get("SESSION_TYPE") != "filesystem":
        return 0

    session_dir = app.config.get("SESSION_FILE_DIR")
    if not session_dir:
        # Flask-Session default when SESSION_FILE_DIR is not configured.
        session_dir = os.path.join(os.getcwd(), "flask_session")

    if not os.path.isdir(session_dir):
        return 0

    deleted = 0
    for entry in os.listdir(session_dir):
        path = os.path.join(session_dir, entry)
        if os.path.isfile(path):
            try:
                os.remove(path)
                deleted += 1
            except OSError:
                continue
    return deleted


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
        user = User(username=username, email=email, role=User.ROLE_REVIEWER)  # type: ignore
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
        user = User(username=username, email=email, role=User.ROLE_ADMIN)  # type: ignore
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
        try:
            db.session.execute(recipe_machines.delete())
        except Exception:
            pass

        Recipe.query.delete()  # noqa: F841
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

            user = User(username=username, email=email, role=User.ROLE_REVIEWER)  # type: ignore
            user.set_password("password123")
            db.session.add(user)
            created_users.append(user)

        admin_username = os.getenv("admin_username", "admin")
        admin_email = os.getenv("admin_email", "admin@example.com")
        admin_password = os.getenv("admin_password", "admin123")

        admin = User(username=admin_username, email=admin_email, role=User.ROLE_ADMIN)  # type: ignore
        admin.set_password(admin_password)
        db.session.add(admin)
        created_users.append(admin)

        db.session.commit()

        reviewers = [
            user
            for user in created_users
            if user.role == User.ROLE_REVIEWER and user.username != "admin"
        ]
        creator_count = min(len(reviewers), max(1, users // 4))
        for creator in random.sample(reviewers, k=creator_count) if reviewers else []:
            creator.role = User.ROLE_CREATOR

        db.session.commit()

        if KitchenMachine.query.count() == 0:
            click.echo(click.style("Adding common kitchen machines...", fg="green"))
            common_machines = [
                ("kookplaat", "Elektrische of gas kookplaat"),
                ("Oven", "Standaard oven voor bakken en braden"),
                ("Magnetron", "Magnetron voor opwarmen en koken"),
                ("Mixer", "Elektrische mixer voor deeg en beslag"),
                ("Blender", "Blender voor smoothies en soepen"),
                ("Staafmixer", "Handstaafmixer"),
                ("Slowcooker", "Slowcooker voor langzaam garen"),
                ("Airfryer", "Heteluchtfriteuse"),
                ("Frituurpan", "voor frituren"),
                ("Deegmachine", "Deegmachine voor pasta en bakken"),
                ("Panini ijzer", "Elektrische grill voor broodjes en vlees"),
                ("Sous-vide", "Sous-vide apparaat voor precisie koken"),
            ]

            for name, description in common_machines:
                machine = KitchenMachine(name=name, description=description)  # type: ignore
                db.session.add(machine)
            db.session.commit()

        # No per-user machine linking required — assume users have all machines
        all_machines = KitchenMachine.query.all()

        # Generate recipes using the realistic generator
        click.echo(f"\nMaak {recipes} recepten aan ...")
        generated = generate_recipes(n=recipes)
        measurements = ["g", "kg", "ml", "l", "el", "tl", "stuks"]

        for rec in generated:
            ingredient_list = []
            for name in rec.get("ingredients", []):
                qty = round(fake.random.uniform(1, 500), 2)
                measurement = random.choice(measurements)
                ingredient_list.append(
                    {"name_": name, "quantity": qty, "measurement": measurement}
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
                        if u.role in (User.ROLE_CREATOR, User.ROLE_ADMIN)
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

            if all_machines and fake.boolean(chance_of_getting_true=70):
                num_req_machines = fake.random_int(min=1, max=min(3, len(all_machines)))
                recipe.required_machines = fake.random_elements(
                    elements=all_machines, length=num_req_machines, unique=True
                )

            db.session.add(recipe)

        db.session.commit()

        # Add random favorites for created users
        try:
            all_recipes = Recipe.query.all()
            if all_recipes:
                for user in created_users:
                    # each user gets 0-6 favorites randomly
                    fav_count = random.randint(0, min(6, len(all_recipes)))
                    if fav_count == 0:
                        continue
                    favs = random.sample(all_recipes, k=fav_count)
                    for r in favs:
                        # avoid duplicates due to seeding logic
                        if not user.favorites.filter_by(id=r.id).first():
                            user.favorites.append(r)
                db.session.commit()
        except Exception:
            # don't fail the whole seed if favorites can't be added
            db.session.rollback()

    @app.cli.command("clear-data")
    def clear_data():
        """Delete all data from the database.

        Usage:
            flask clear-data
        """
        click.echo("Alle data uit de database verwijderen...")

        Recipe.query.delete()  # noqa: F841
        User.query.delete()  # noqa: F841

        db.session.commit()

    @app.cli.command("db-stats")
    def db_stats():
        """Display database statistics.

        Usage:
            flask db-stats
        """
        num_users = User.query.count()
        num_active_users = User.query.filter_by(is_active=True).count()
        num_deactivated_users = User.query.filter_by(is_active=False).count()
        num_reviewers = User.query.filter_by(role=User.ROLE_REVIEWER).count()
        num_creators = User.query.filter_by(role=User.ROLE_CREATOR).count()
        num_admins = User.query.filter_by(role=User.ROLE_ADMIN).count()
        num_recipes = Recipe.query.count()
        num_machines = KitchenMachine.query.count()

        click.echo(click.style("\n=== Database Statistieken ===", fg="cyan", bold=True))
        click.echo(f"Gebruikers:         {num_users}")
        click.echo(f"  - Actief:         {num_active_users}")
        click.echo(f"  - Gedeactiveerd:  {num_deactivated_users}")
        click.echo(f"  - Reviewers:      {num_reviewers}")
        click.echo(f"  - Creators:       {num_creators}")
        click.echo(f"  - Admins:         {num_admins}")
        click.echo(f"Recepten:           {num_recipes}")
        click.echo(f"Keukenapparatuur:   {num_machines}")

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

    @app.cli.command("add-machine")
    @click.argument("name")
    @click.option(
        "--description", default="", help="Description of the kitchen machine"
    )
    def add_machine(name, description):
        """Add a kitchen machine to the database.

        Usage:
            flask add-machine "Oven"
            flask add-machine "Mixer" --description "Electric hand mixer"
        """
        # Check if machine already exists
        existing = KitchenMachine.query.filter_by(name=name).first()
        if existing:
            click.echo(
                click.style(f'Fout: Keukenapparatuur "{name}" bestaat al.', fg="red")
            )
            return

        machine = KitchenMachine(name=name, description=description)  # type: ignore
        db.session.add(machine)
        db.session.commit()

        click.echo(click.style(f"✓ Keukenapparatuur toegevoegd: {name}", fg="green"))

    @app.cli.command("list-machines")
    def list_machines():
        """List all kitchen machines in the database.

        Usage:
            flask list-machines
        """
        machines = KitchenMachine.query.order_by(KitchenMachine.name).all()

        if not machines:
            click.echo("Geen keukenapparatuur gevonden.")
            return

        click.echo(click.style("\n=== Keukenapparatuur ===", fg="cyan", bold=True))
        for machine in machines:
            desc = f" - {machine.description}" if machine.description else ""
            click.echo(f"{machine.id}. {machine.name}{desc}")

    @app.cli.command("backup")
    def backup_database():
        """Creates a backup of the configured SQLite database as backup.db."""
        env = os.getenv("FLASK_ENV", "development")
        app_config = config[env]
        db_uri = app_config.SQLALCHEMY_DATABASE_URI

        db_path = _get_db_file_from_uri(db_uri)
        if not os.path.exists(db_path):
            raise click.ClickException(f"Database file not found: {db_path}")

        backup_path = os.path.join(os.path.dirname(db_path) or ".", "backup.db")
        shutil.copy2(db_path, backup_path)

        now = datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%d-%m-%Y %H:%M:%S")
        rel_db = os.path.relpath(db_path, start=BASE_DIR)
        rel_backup = os.path.relpath(backup_path, start=BASE_DIR)
        print(f"Database backed up ({now}): {rel_db} -> {rel_backup}")

    @app.cli.command("restore")
    def restore_database():
        env = os.getenv("FLASK_ENV", "development")
        app_config = config[env]
        db_uri = app_config.SQLALCHEMY_DATABASE_URI

        db_path = _get_db_file_from_uri(db_uri)
        backup_path = os.path.join(os.path.dirname(db_path) or ".", "backup.db")

        if not os.path.exists(backup_path):
            raise click.ClickException(f"Backup file not found: {backup_path}")

        db.session.remove()
        db.engine.dispose()

        shutil.copy2(backup_path, db_path)

        db.engine.dispose()
        deleted_sessions = _clear_filesystem_sessions(app)

        now = datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%d-%m-%Y %H:%M:%S")
        rel_db = os.path.relpath(db_path, start=BASE_DIR)
        rel_backup = os.path.relpath(backup_path, start=BASE_DIR)
        print(
            f"Database restored ({now}): {rel_backup} -> {rel_db}. "
            f"Cleared {deleted_sessions} server session(s); users must log in again."
        )
