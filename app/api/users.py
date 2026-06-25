from __future__ import annotations

from app import db
from app.api.common import ApiError
from app.models import Recipe, User


def register_user(*, username: str, email: str, password: str) -> User:
    """Create a new user account."""
    if User.query.filter_by(username=username).first():
        raise ApiError("Gebruikersnaam al in gebruik. Kies een andere.", 400)
    if User.query.filter_by(email=email).first():
        raise ApiError("E-mail al geregistreerd. Gebruik een ander e-mailadres.", 400)

    user = User(username=username, email=email)
    user.set_password(password)
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
    if target.role == User.ROLE_FIJNPROEVER:
        return target

    target.role -= 1
    target.creator_request_pending = False
    db.session.commit()
    return target
