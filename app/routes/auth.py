from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import login_manager
from app.api import (
    ApiError,
    register_user,
    submit_creator_request,
    update_profile,
)
from app.forms import LoginForm, ProfileEditForm, RegistrationForm
from app.models import User

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
    if form.validate_on_submit():
        try:
            register_user(
                username=form.username.data,
                email=form.email.data,
                password=form.password.data,
            )
        except ApiError as error:
            flash(error.message, "danger")
            return render_template("auth/register.html", form=form)

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
            if not user.is_active:
                flash("Je account is gedeactiveerd.", "danger")
                return render_template("auth/login.html", form=form)
            if not login_user(user):
                flash("Inloggen mislukt voor dit account.", "danger")
                return render_template("auth/login.html", form=form)
            next_page = request.args.get("next")
            flash(f"Welkom terug, {user.username}!", "success")
            return redirect(next_page) if next_page else redirect(url_for("main.index"))
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

    if form.validate_on_submit():
        try:
            update_profile(
                user=current_user,
                username=form.username.data,
                email=form.email.data,
                current_password=form.current_password.data,
                new_password=form.new_password.data,
            )
        except ApiError as error:
            flash(error.message, "danger")
            return render_template("auth/profile_edit.html", form=form)

        flash("Profiel succesvol bijgewerkt!", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile_edit.html", form=form)


@auth_bp.route("/request-creator", methods=["POST"])
@login_required
def request_creator():
    if not current_user.is_active:
        return redirect(url_for("auth.profile"))
    if current_user.role != User.ROLE_FIJNPROEVER:
        flash("Alleen reviewers kunnen een creator-aanvraag doen.", "info")
        return redirect(url_for("auth.profile"))
    if current_user.creator_request_pending:
        flash("Je creator-aanvraag staat al open.", "info")
        return redirect(url_for("auth.profile"))

    try:
        submit_creator_request(current_user)
    except ApiError as error:
        flash(error.message, "danger")
        return redirect(url_for("auth.profile"))

    flash("Je aanvraag om creator te worden is verstuurd.", "success")
    return redirect(url_for("auth.profile"))
