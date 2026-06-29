from datetime import datetime
from typing import cast

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db, login_manager
from app.api import (
    ApiError,
    cleanup_expired_otc_codes,
    create_registration_otc,
    register_user,
    submit_creator_request,
    update_profile,
)
from app.forms import LoginForm, OTCCreateForm, ProfileEditForm, RegistrationForm
from app.models import OTC, User
from utils import require_active_admin

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

    form = RegistrationForm(
        data={
            "otc": request.args.get("otc", "") or request.args.get("OTC", ""),
        }
    )
    if form.validate_on_submit():
        try:
            username = form.username.data
            email = form.email.data
            password = form.password.data
            otc = form.otc.data
            if not username or not email or not password:
                raise ApiError("Controleer de invoer.", 400)
            register_user(
                username=username,
                email=email,
                password=password,
                one_time_code=otc,
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
    user = cast(User, current_user)
    form = ProfileEditForm(obj=user)

    if form.validate_on_submit():
        try:
            username = form.username.data
            email = form.email.data
            if not username or not email:
                raise ApiError("Controleer de invoer.", 400)
            update_profile(
                user=user,
                username=username,
                email=email,
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
        submit_creator_request(cast(User, current_user))
    except ApiError as error:
        flash(error.message, "danger")
        return redirect(url_for("auth.profile"))

    flash("Je aanvraag om creator te worden is verstuurd.", "success")
    return redirect(url_for("auth.profile"))


@auth_bp.route("/profile/otc", methods=["GET", "POST"])
@login_required
def manage_otc():
    """Create and inspect OTCs for learner registrations."""
    admin_user = cast(User, current_user)
    require_active_admin(admin_user)
    cleanup_expired_otc_codes()

    form = OTCCreateForm()
    created_otc = session.pop("created_otc", None)
    registration_link = session.pop("registration_link", None)

    if created_otc:
        created_otc["expires_at"] = datetime.fromisoformat(created_otc["expires_at"])

    if form.validate_on_submit():
        try:
            expires_in_hours = form.expires_in_hours.data
            if expires_in_hours is None:
                raise ApiError("Controleer de invoer.", 400)
            created_otc = create_registration_otc(
                expires_in_hours=expires_in_hours,
                purpose=form.purpose.data,
            )
        except ApiError as error:
            flash(error.message, "danger")
        else:
            registration_link = url_for("auth.register", otc=created_otc.code, _external=True)
            session["created_otc"] = {
                "code": created_otc.code,
                "purpose": created_otc.purpose,
                "expires_at": created_otc.expires_at.isoformat(),
            }
            session["registration_link"] = registration_link
            flash("OTC aangemaakt voor een leerling kok-registratie.", "success")
            return redirect(url_for("auth.manage_otc"))

    active_otcs = OTC.query.order_by(OTC.expires_at.asc(), OTC.created_at.desc()).all()
    return render_template(
        "auth/otc_admin.html",
        form=form,
        active_otcs=active_otcs,
        created_otc=created_otc,
        registration_link=registration_link,
    )


@auth_bp.route("/profile/otc/<string:code>/delete", methods=["POST"])
@login_required
def delete_otc(code: str):
    """Delete an OTC from the dashboard."""
    admin_user = cast(User, current_user)
    require_active_admin(admin_user)
    otc = OTC.query.get_or_404(code)
    db.session.delete(otc)
    db.session.commit()
    flash(f"OTC {code} verwijderd.", "success")
    return redirect(url_for("auth.manage_otc"))
