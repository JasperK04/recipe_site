from __future__ import annotations

from typing import cast

from flask import jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from app import db
from app.api import api_bp
from app.api.common import ApiError
from app.models import Credential, Recipe, User
from app.services.credentials import (
    claim_credential,
    cleanup_expired_credentials,
    find_usable_credential,
    issue_credential,
    revoke_active_credentials,
)
from app.services.email import send_creator_request_notification
from utils import require_active_admin
from utils.moderation import moderate_username


def cleanup_expired_otc_codes() -> int:
    """Delete expired registration credentials and return the number removed."""
    return cleanup_expired_credentials()


def _normalize_otc_code(value: str | None) -> str | None:
    code = (value or "").strip()
    return code or None


PASSWORD_RESET_PURPOSE = "password_reset"
REGISTRATION_PURPOSE = "registration_invitation"
PASSWORD_RESET_MESSAGE = (
    "Als een account overeenkomt met de opgegeven gegevens, sturen we herstel-instructies."
)


def _find_user_by_identifier(identifier: str | None) -> User | None:
    """Find an account by username or email without exposing which matched."""
    normalized = (identifier or "").strip()
    if not normalized or len(normalized) > 120:
        return None
    return User.query.filter(
        or_(
            User.username == normalized,
            func.lower(User.email) == normalized.lower(),
        )
    ).first()


def create_password_reset_credential(user: User) -> tuple[Credential, str]:
    """Create a short-lived, single-use password reset credential."""
    cleanup_expired_credentials()
    revoke_active_credentials(
        purpose=PASSWORD_RESET_PURPOSE, subject_type="user", subject_id=user.id
    )
    credential, token = issue_credential(
        purpose=PASSWORD_RESET_PURPOSE,
        subject_type="user",
        subject_id=user.id,
    )
    db.session.commit()
    return credential, token


def get_valid_password_reset_credential(token: str | None) -> Credential | None:
    credential = find_usable_credential(purpose=PASSWORD_RESET_PURPOSE, token=token)
    if not credential or credential.subject_type != "user" or not credential.subject_user:
        return None
    return credential


def get_valid_password_reset_credential_by_id(credential_id: int | None) -> Credential | None:
    if not credential_id:
        return None
    credential = db.session.get(Credential, credential_id)
    if (
        not credential
        or credential.purpose != PASSWORD_RESET_PURPOSE
        or credential.subject_type != "user"
        or not credential.subject_user
        or not credential.is_usable()
    ):
        return None
    return credential


def request_password_reset(identifier: str | None) -> None:
    """Issue a reset email where possible; callers always return the same reply."""
    user = _find_user_by_identifier(identifier)
    if not user:
        return
    _, token = create_password_reset_credential(user)
    # Import locally to avoid a module cycle and keep mail failures out of the
    # public response, which must not disclose account existence.
    from app.services.email import send_password_reset_email

    send_password_reset_email(user, token)


def complete_password_reset(
    *,
    token: str | None = None,
    credential_id: int | None = None,
    new_password: str | None,
    confirm_password: str | None,
) -> User:
    """Validate a reset credential again and consume it atomically with the password change."""
    if not new_password or len(new_password) < 6:
        raise ApiError("Wachtwoord moet minimaal 6 tekens lang zijn.", 400)
    if new_password != confirm_password:
        raise ApiError("Wachtwoorden moeten overeenkomen.", 400)
    credential = (
        get_valid_password_reset_credential(token)
        if token
        else get_valid_password_reset_credential_by_id(credential_id)
    )
    if not credential:
        raise ApiError("Deze herstel-link is ongeldig of verlopen.", 400)

    user = credential.subject_user
    if user is None:
        raise ApiError("Deze herstel-link is ongeldig of verlopen.", 400)
    # Claim the credential in the same transaction as the password change. The
    # conditional update prevents two concurrent requests from consuming one
    # reset link successfully.
    if not claim_credential(credential):
        db.session.rollback()
        raise ApiError("Deze herstel-link is ongeldig of verlopen.", 400)
    user.set_password(new_password)
    db.session.commit()
    return user


def create_registration_otc(
    *, expires_in_hours: int, purpose: str | None = None
) -> tuple[Credential, str]:
    """Create a registration invitation credential."""
    cleanup_expired_otc_codes()
    credential, token = issue_credential(
        purpose=REGISTRATION_PURPOSE,
        subject_type="registration",
        lifetime=expires_in_hours,
        metadata={"label": (purpose or "").strip() or None},
    )
    db.session.commit()
    return credential, token


def register_user(
    *,
    username: str,
    email: str,
    password: str,
    one_time_code: str | None = None,
) -> User:
    """Create a new user account."""
    username_result = moderate_username(username)
    errors = username_result.messages
    if User.query.filter_by(username=username).first():
        errors.append("Gebruikersnaam al in gebruik. Kies een andere.")
    if errors:
        raise ApiError(" ".join(errors), 400)
    if User.query.filter_by(email=email).first():
        raise ApiError("E-mail al geregistreerd. Gebruik een ander e-mailadres.", 400)

    normalized_code = _normalize_otc_code(one_time_code)
    credential: Credential | None = None
    if normalized_code:
        cleanup_expired_otc_codes()
        credential = find_usable_credential(
            purpose=REGISTRATION_PURPOSE, token=normalized_code
        )
        if not credential or credential.subject_type != "registration":
            raise ApiError("Ongeldige of verlopen OTC-code.", 400)

    user = User(username=username, email=email)
    user.set_password(password)
    if credential:
        user.role = User.ROLE_LEERLING_KOK
        if not claim_credential(credential):
            db.session.rollback()
            raise ApiError("Ongeldige of verlopen OTC-code.", 400)

    db.session.add(user)
    db.session.commit()
    return user


def update_profile(
    *,
    user: User,
    username: str,
    email: str,
    current_password: str | None = None,
    new_password: str | None = None,
) -> User:
    """Update the current user's profile and optional password."""
    if username != user.username:
        username_result = moderate_username(username)
        errors = username_result.messages
        existing_username = User.query.filter_by(username=username).first()
        if existing_username and existing_username.id != user.id:
            errors.append("Gebruikersnaam al in gebruik. Kies een andere.")
        if errors:
            raise ApiError(" ".join(errors), 400)

    existing_email = User.query.filter_by(email=email).first()
    if existing_email and existing_email.id != user.id:
        raise ApiError("E-mail al geregistreerd. Gebruik een ander e-mailadres.", 400)

    user.username = username
    user.email = email

    if new_password:
        if not current_password:
            raise ApiError(
                "Vul je huidige wachtwoord in om het wachtwoord te wijzigen.", 400
            )
        if not user.check_password(current_password):
            raise ApiError("Huidig wachtwoord is onjuist.", 400)
        user.set_password(new_password)

    db.session.commit()
    return user


def submit_creator_request(user: User) -> User:
    """Persist a creator access request."""
    if not user.is_active:
        raise ApiError("Alleen actieve accounts kunnen een creator-aanvraag doen.", 403)
    if user.role != User.ROLE_FIJNPROEVER:
        raise ApiError("Alleen reviewers kunnen een creator-aanvraag doen.", 400)
    if user.creator_request_pending:
        raise ApiError("Je creator-aanvraag staat al open.", 400)

    user.creator_request_pending = True
    db.session.commit()
    send_creator_request_notification(user)
    return user


def deactivate_user(*, actor: User, target: User) -> User:
    """Deactivate a user and temporarily deactivate their recipes."""
    if target.id == actor.id:
        raise ApiError("Je kunt je eigen account niet deactiveren.", 400)
    if target.role == User.ROLE_CHEF_DE_CUISINE:
        raise ApiError("Andere admins deactiveren is niet toegestaan.", 400)
    if not target.is_active:
        return target

    target.is_active = False
    target.creator_request_pending = False

    for recipe in target.recipes.all():
        if recipe.status != Recipe.STATUS_DEACTIVATED:
            recipe.status_before_deactivation = recipe.status
            recipe.status = Recipe.STATUS_DEACTIVATED

    db.session.commit()
    return target


def reactivate_user(target: User) -> User:
    """Reactivate a user and restore their recipes."""
    if target.is_active:
        return target

    target.is_active = True

    for recipe in target.recipes.all():
        if recipe.status != Recipe.STATUS_DEACTIVATED:
            continue

        if recipe.status_before_deactivation in (
            Recipe.STATUS_PUBLIC,
            Recipe.STATUS_PRIVATE,
        ):
            recipe.status = recipe.status_before_deactivation
        else:
            recipe.status = Recipe.STATUS_PRIVATE

        recipe.status_before_deactivation = None

    db.session.commit()
    return target


def promote_user(target: User) -> User:
    """Promote a non-admin user."""
    if target.role == User.ROLE_CHEF_DE_CUISINE:
        raise ApiError("Admins kunnen niet gepromoveerd worden.", 400)
    if target.role >= User.ROLE_SOUS_CHEF:
        return target

    target.role += 1
    target.creator_request_pending = False
    db.session.commit()
    return target


def demote_user(target: User) -> User:
    """Demote a non-admin user."""
    if target.role == User.ROLE_CHEF_DE_CUISINE:
        raise ApiError("Admins kunnen niet gedegradeerd worden via deze actie.", 400)
    if target.role == User.ROLE_FIJNPROEVER and target.creator_request_pending:
        target.creator_request_pending = False
        db.session.commit()
        return target
    if target.role == User.ROLE_FIJNPROEVER:
        return target

    target.role -= 1
    target.creator_request_pending = False
    db.session.commit()
    return target


def pending_creator_request_count() -> int:
    """Return the number of open creator promotion requests."""
    return User.query.filter_by(creator_request_pending=True).count()


def _user_row_response(user: User):
    return jsonify(
        {
            "status": "ok",
            "pending_creator_requests": pending_creator_request_count(),
            "html": render_template(
                "components/user_table_row.html",
                user=user,
                current_user=current_user,
            ),
        }
    )


def _json_error(error: ApiError):
    return jsonify({"status": "error", "message": error.message}), error.status_code


def _request_value(name: str) -> str | None:
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        value = payload.get(name)
    else:
        value = request.form.get(name)
    return value if isinstance(value, str) else None


@api_bp.route("/password-reset/request", methods=["POST"])
def password_reset_request_endpoint():
    """Always return the same response to prevent account enumeration."""
    request_password_reset(_request_value("identifier"))
    return jsonify({"message": PASSWORD_RESET_MESSAGE})


@api_bp.route("/password-reset/verify", methods=["POST"])
def password_reset_verify_endpoint():
    """A positive result only proves possession of this still-valid token."""
    return jsonify(
        {"valid": get_valid_password_reset_credential(_request_value("token")) is not None}
    )


@api_bp.route("/password-reset/complete", methods=["POST"])
def password_reset_complete_endpoint():
    try:
        complete_password_reset(
            token=_request_value("token"),
            new_password=_request_value("newPassword") or _request_value("new_password"),
            confirm_password=_request_value("confirmPassword")
            or _request_value("confirm_password"),
        )
    except ApiError as error:
        return _json_error(error)
    return jsonify({"message": "Je wachtwoord is gewijzigd. Je kunt nu inloggen."})


@api_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@login_required
def deactivate_user_endpoint(user_id):
    actor = cast(User, current_user)
    require_active_admin(actor)
    target = User.query.get_or_404(user_id)

    try:
        deactivate_user(actor=actor, target=target)
    except ApiError as error:
        return _json_error(error)

    return _user_row_response(target)


@api_bp.route("/users/<int:user_id>/reactivate", methods=["POST"])
@login_required
def reactivate_user_endpoint(user_id):
    actor = cast(User, current_user)
    require_active_admin(actor)
    target = User.query.get_or_404(user_id)

    reactivate_user(target)
    return _user_row_response(target)


@api_bp.route("/users/<int:user_id>/promote", methods=["POST"])
@login_required
def promote_user_endpoint(user_id):
    actor = cast(User, current_user)
    require_active_admin(actor)
    target = User.query.get_or_404(user_id)

    try:
        promote_user(target)
    except ApiError as error:
        return _json_error(error)

    return _user_row_response(target)


@api_bp.route("/users/<int:user_id>/demote", methods=["POST"])
@login_required
def demote_user_endpoint(user_id):
    actor = cast(User, current_user)
    require_active_admin(actor)
    target = User.query.get_or_404(user_id)

    try:
        demote_user(target)
    except ApiError as error:
        return _json_error(error)

    return _user_row_response(target)
