from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import cast

from flask import jsonify, render_template
from flask_login import current_user, login_required

from app import db
from app.api import api_bp
from app.api.common import ApiError
from app.models import OTC, Recipe, User
from app.services.email import send_creator_request_notification
from utils import require_active_admin


def cleanup_expired_otc_codes() -> int:
    """Delete expired OTC records and return the number removed."""
    now = datetime.now(timezone.utc)
    removed = OTC.query.filter(OTC.expires_at <= now).delete(synchronize_session=False)
    if removed:
        db.session.commit()
    return removed


def _normalize_otc_code(value: str | None) -> str | None:
    code = (value or "").strip()
    return code or None


def generate_otc_code() -> str:
    """Generate an 8 character OTC code."""
    alphabet = string.ascii_lowercase + string.digits
    token = "".join(secrets.choice(alphabet) for _ in range(8))
    return token


def create_registration_otc(
    *, expires_in_hours: int, purpose: str | None = None
) -> OTC:
    """Create a new OTC for leerling kok registration."""
    cleanup_expired_otc_codes()

    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

    for _ in range(20):
        code = generate_otc_code()
        if OTC.query.filter_by(code=code).first():
            continue

        otc = OTC(
            code=code,
            purpose=(purpose or "").strip() or None,
            expires_at=expires_at,
        )
        db.session.add(otc)
        db.session.commit()
        return otc

    raise ApiError("Kon geen unieke OTC-code genereren. Probeer het opnieuw.", 500)


def register_user(
    *,
    username: str,
    email: str,
    password: str,
    one_time_code: str | None = None,
) -> User:
    """Create a new user account."""
    if User.query.filter_by(username=username).first():
        raise ApiError("Gebruikersnaam al in gebruik. Kies een andere.", 400)
    if User.query.filter_by(email=email).first():
        raise ApiError("E-mail al geregistreerd. Gebruik een ander e-mailadres.", 400)

    otc: OTC | None = None
    normalized_code = _normalize_otc_code(one_time_code)
    if normalized_code:
        cleanup_expired_otc_codes()
        otc = OTC.query.filter_by(code=normalized_code).first()
        if not otc:
            raise ApiError("Ongeldige of verlopen OTC-code.", 400)

    user = User(username=username, email=email)
    user.set_password(password)
    if otc:
        user.role = User.ROLE_LEERLING_KOK
        db.session.delete(otc)

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
    existing_username = User.query.filter_by(username=username).first()
    if existing_username and existing_username.id != user.id:
        raise ApiError("Gebruikersnaam al in gebruik. Kies een andere.", 400)

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

    setattr(target, "is_active", False)
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

    setattr(target, "is_active", True)

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


def _user_row_response(user: User):
    return jsonify(
        {
            "status": "ok",
            "html": render_template(
                "components/user_table_row.html",
                user=user,
                current_user=current_user,
            ),
        }
    )


def _json_error(error: ApiError):
    return jsonify({"status": "error", "message": error.message}), error.status_code


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
