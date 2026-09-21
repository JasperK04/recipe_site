from typing import cast

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, or_

from app import db, login_manager
from app.api import (
    ApiError,
    complete_password_reset,
    register_user,
    submit_creator_request,
    update_profile,
)
from app.api import (
    request_password_reset as issue_password_reset,
)
from app.api.users import (
    get_valid_password_reset_credential,
    get_valid_password_reset_credential_by_id,
)
from app.forms import (
    LoginForm,
    PasswordResetForm,
    PasswordResetRequestForm,
    ProfileEditForm,
    RegistrationForm,
)
from app.models import User
from app.navigation import safe_redirect_target

auth_bp = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return db.session.get(User, int(user_id))


@auth_bp.route("/registreren", methods=["GET", "POST"])
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


@auth_bp.route("/inloggen", methods=["GET", "POST"])
def login():
    """User login route."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    next_page = safe_redirect_target(request.values.get("next"))
    form = LoginForm()
    if form.validate_on_submit():
        identifier = (form.username.data or "").strip()
        user = User.query.filter(
            or_(
                User.username == identifier,
                func.lower(User.email) == identifier.lower(),
            )
        ).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash("Je account is gedeactiveerd.", "danger")
                return render_template("auth/login.html", form=form)
            if not login_user(user):
                flash("Inloggen mislukt voor dit account.", "danger")
                return render_template("auth/login.html", form=form)
            flash(f"Welkom terug, {user.username}!", "success")
            return redirect(next_page) if next_page else redirect(url_for("main.index"))
        flash("Ongeldige gebruikersnaam of wachtwoord.", "danger")

    return render_template("auth/login.html", form=form, next_page=next_page)


@auth_bp.route("/wachtwoord-vergeten", methods=["GET", "POST"])
def request_password_reset():
    """Public password-recovery page with an enumeration-safe outcome."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        issue_password_reset(form.identifier.data)
        flash(
            "Als een account overeenkomt met de opgegeven gegevens, sturen we herstel-instructies.",
            "info",
        )
        return redirect(url_for("auth.request_password_reset"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/wachtwoord-resetten", methods=["GET", "POST"])
def reset_password():
    """Show and consume a password-reset credential bound to the server session."""
    if request.method == "GET":
        token = request.args.get("token")
        credential = get_valid_password_reset_credential(token) if token else None
        if credential:
            session["password_reset_credential_id"] = credential.id
        else:
            credential = get_valid_password_reset_credential_by_id(
                session.get("password_reset_credential_id")
            )
        if not credential:
            session.pop("password_reset_credential_id", None)
            return render_template(
                "auth/reset_password.html", form=PasswordResetForm(), token_valid=False
            )
    else:
        credential = get_valid_password_reset_credential_by_id(
            session.get("password_reset_credential_id")
        )
        if not credential:
            return render_template(
                "auth/reset_password.html", form=PasswordResetForm(), token_valid=False
            )

    form = PasswordResetForm()
    subject_user = credential.subject_user
    if subject_user is None:
        abort(404)
    if form.validate_on_submit():
        try:
            complete_password_reset(
                credential_id=credential.id,
                new_password=form.new_password.data,
                confirm_password=form.confirm_password.data,
            )
        except ApiError as error:
            flash(error.message, "danger")
            return render_template(
                "auth/reset_password.html",
                form=form,
                token_valid=True,
                reset_email=subject_user.email,
            )
        session.pop("password_reset_credential_id", None)
        flash("Je wachtwoord is gewijzigd. Je kunt nu inloggen.", "success")
        return redirect(url_for("auth.login"))
    return render_template(
        "auth/reset_password.html",
        form=form,
        token_valid=True,
        reset_email=subject_user.email,
    )


@auth_bp.route("/uitloggen")
@login_required
def logout():
    """User logout route."""
    logout_user()
    flash("U bent uitgelogd.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/profiel")
@login_required
def profile():
    """Read-only profile view."""
    return render_template("auth/profile.html")


@auth_bp.route("/profiel/bewerken", methods=["GET", "POST"])
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


@auth_bp.route("/maker-aanvragen", methods=["POST"])
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


@auth_bp.route("/profiel/otc", methods=["GET", "POST"])
@login_required
def manage_otc():
    return redirect(url_for("admin.manage_otc"), code=302)


@auth_bp.route("/profiel/otc/<int:credential_id>/verwijderen", methods=["POST"])
@login_required
def delete_otc(credential_id: int):
    return redirect(url_for("admin.delete_otc", credential_id=credential_id), code=307)
