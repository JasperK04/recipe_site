from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db, login_manager
from app.forms import LoginForm, ProfileEditForm, RegistrationForm
from app.models import KitchenMachine, User

auth_bp = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return User.query.get(int(user_id))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """User registration route."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegistrationForm()
    # Populate kitchen machines choices
    machines = KitchenMachine.query.order_by(KitchenMachine.name).all()
    form.kitchen_machines.choices = [(m.id, m.name) for m in machines]

    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)  # type: ignore
        user.set_password(form.password.data)

        # Add selected kitchen machines
        selected_machine_ids = form.kitchen_machines.data
        if selected_machine_ids:
            selected_machines: list[KitchenMachine] = KitchenMachine.query.filter(
                KitchenMachine.id.in_(selected_machine_ids)
            ).all()
            user.kitchen_machines.extend(selected_machines)

        db.session.add(user)
        db.session.commit()
        flash("Registratie geslaagd! Log alstublieft in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User login route."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get("next")
            flash(f"Welkom terug, {user.username}!", "success")
            return redirect(next_page) if next_page else redirect(url_for("main.index"))
        else:
            flash("Ongeldige gebruikersnaam of wachtwoord.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    """User logout route."""
    logout_user()
    flash("U bent uitgelogd.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/profile")
@login_required
def profile():
    """Read-only profile view."""
    return render_template("auth/profile.html")


@auth_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    """Edit profile and optionally change password."""
    form = ProfileEditForm(obj=current_user)

    # Populate kitchen machines choices
    machines = KitchenMachine.query.order_by(KitchenMachine.name).all()
    form.kitchen_machines.choices = [(m.id, m.name) for m in machines]

    if request.method == "GET":
        form.kitchen_machines.data = [m.id for m in current_user.kitchen_machines]

    if form.validate_on_submit():
        # Update basic fields
        current_user.username = form.username.data  # type: ignore
        current_user.email = form.email.data  # type: ignore

        # Update machines
        selected_machine_ids = form.kitchen_machines.data or []
        selected_machines: list[KitchenMachine] = (
            KitchenMachine.query.filter(
                KitchenMachine.id.in_(selected_machine_ids)
            ).all()
            if selected_machine_ids
            else []
        )
        current_user.kitchen_machines.clear()
        current_user.kitchen_machines.extend(selected_machines)

        # Optional password change
        if form.new_password.data:
            current_user.set_password(form.new_password.data)

        db.session.commit()
        flash("Profiel succesvol bijgewerkt!", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile_edit.html", form=form)
