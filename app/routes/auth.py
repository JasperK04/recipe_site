from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db, login_manager
from app.forms import LoginForm, ProfileEditForm, RegistrationForm
from app.models import Recipe, User
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

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)  # type: ignore
        user.set_password(form.password.data)

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
            if not user.is_active:
                flash("Je account is gedeactiveerd.", "danger")
                return render_template("auth/login.html", form=form)
            if not login_user(user):
                flash("Inloggen mislukt voor dit account.", "danger")
                return render_template("auth/login.html", form=form)
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

    if request.method == "GET":
        pass

    if form.validate_on_submit():
        # Update basic fields
        current_user.username = form.username.data  # type: ignore
        current_user.email = form.email.data  # type: ignore

        # Optional password change
        if form.new_password.data:
            current_user.set_password(form.new_password.data)

        db.session.commit()
        flash("Profiel succesvol bijgewerkt!", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile_edit.html", form=form)


@auth_bp.route("/request-creator", methods=["POST"])
@login_required
def request_creator():
    if not current_user.is_active:
        abort(403)
    if current_user.role != User.ROLE_REVIEWER:
        flash("Alleen reviewers kunnen een creator-aanvraag doen.", "info")
        return redirect(url_for("auth.profile"))
    if current_user.creator_request_pending:
        flash("Je creator-aanvraag staat al open.", "info")
        return redirect(url_for("auth.profile"))

    current_user.creator_request_pending = True
    db.session.commit()
    flash("Je aanvraag om creator te worden is verstuurd.", "success")
    return redirect(url_for("auth.profile"))


@auth_bp.route("/admin/users")
@login_required
def admin_users():
    require_active_admin(current_user)
    users = User.query.order_by(db.text("is_active DESC"), User.username.asc()).all()
    return render_template("auth/admin_users.html", users=users)


@auth_bp.route("/admin/users/<int:user_id>/deactivate", methods=["POST"])
@login_required
def deactivate_user(user_id):
    require_active_admin(current_user)
    target = User.query.get_or_404(user_id)

    if target.id == current_user.id:
        flash("Je kunt je eigen account niet deactiveren.", "warning")
        return redirect(url_for("auth.admin_users"))
    if target.role == User.ROLE_ADMIN:
        flash("Andere admins deactiveren is niet toegestaan.", "warning")
        return redirect(url_for("auth.admin_users"))
    if not target.is_active:
        flash(f"{target.username} is al gedeactiveerd.", "info")
        return redirect(url_for("auth.admin_users"))

    target.is_active = False
    target.creator_request_pending = False
    for recipe in target.recipes.all():
        if recipe.status != Recipe.STATUS_DEACTIVATED:
            recipe.status_before_deactivation = recipe.status
            recipe.status = Recipe.STATUS_DEACTIVATED

    db.session.commit()
    flash(f"Gebruiker {target.username} is gedeactiveerd.", "success")
    return redirect(url_for("auth.admin_users"))


@auth_bp.route("/admin/users/<int:user_id>/reactivate", methods=["POST"])
@login_required
def reactivate_user(user_id):
    require_active_admin(current_user)
    target = User.query.get_or_404(user_id)
    if target.is_active:
        flash(f"{target.username} is al actief.", "info")
        return redirect(url_for("auth.admin_users"))

    target.is_active = True
    for recipe in target.recipes.all():
        if recipe.status != Recipe.STATUS_DEACTIVATED:
            continue
        if recipe.status_before_deactivation in (
            Recipe.STATUS_PUBLIC,
            Recipe.STATUS_DRAFT,
        ):
            recipe.status = recipe.status_before_deactivation
        else:
            recipe.status = Recipe.STATUS_DRAFT
        recipe.status_before_deactivation = None

    db.session.commit()
    flash(f"Gebruiker {target.username} is opnieuw geactiveerd.", "success")
    return redirect(url_for("auth.admin_users"))


@auth_bp.route("/admin/users/<int:user_id>/promote", methods=["POST"])
@login_required
def promote_user(user_id):
    require_active_admin(current_user)
    target = User.query.get_or_404(user_id)

    if target.role == User.ROLE_ADMIN:
        flash("Admins kunnen niet gepromoveerd worden.", "info")
        return redirect(url_for("auth.admin_users"))
    if target.role == User.ROLE_CREATOR:
        flash(f"{target.username} is al creator.", "info")
        return redirect(url_for("auth.admin_users"))

    target.role = User.ROLE_CREATOR
    target.creator_request_pending = False
    db.session.commit()
    flash(f"{target.username} is gepromoveerd naar creator.", "success")
    return redirect(url_for("auth.admin_users"))


@auth_bp.route("/admin/users/<int:user_id>/demote", methods=["POST"])
@login_required
def demote_user(user_id):
    require_active_admin(current_user)
    target = User.query.get_or_404(user_id)

    if target.role == User.ROLE_ADMIN:
        flash("Admins kunnen niet gedegradeerd worden via deze actie.", "warning")
        return redirect(url_for("auth.admin_users"))
    if target.role == User.ROLE_REVIEWER:
        flash(f"{target.username} is al reviewer.", "info")
        return redirect(url_for("auth.admin_users"))

    target.role = User.ROLE_REVIEWER
    target.creator_request_pending = False
    db.session.commit()
    flash(f"{target.username} is gedegradeerd naar reviewer.", "success")
    return redirect(url_for("auth.admin_users"))
