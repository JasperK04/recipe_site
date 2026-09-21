from __future__ import annotations

import hashlib
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate
from typing import cast

from flask import current_app, render_template, url_for

from app import db
from app.models import Recipe, User
from utils.moderation import ModerationResult


@dataclass(frozen=True, slots=True)
class Email:
    subject: str
    recipient: str
    html_body: str
    sender_fallback: str = "recipient"
    error_message: str = "Failed to send email"

    def send(self) -> bool:
        return EmailFactory.send(self)


class EmailFactory:
    """Create application emails and own all delivery infrastructure."""

    @staticmethod
    def create(
        *,
        subject: str,
        recipient: str,
        template: str,
        sender_fallback: str = "recipient",
        error_message: str = "Failed to send email",
        **context: object,
    ) -> Email:
        context.setdefault("site_url", url_for("main.index", _external=True))
        return Email(
            subject=subject,
            recipient=recipient,
            html_body=render_template(template, subject=subject, **context),
            sender_fallback=sender_fallback,
            error_message=error_message,
        )

    @staticmethod
    def send(email: Email) -> bool:
        settings = _mail_settings()
        server = settings["server"]
        sender = settings["sender"] or settings[email.sender_fallback]
        if not server or not email.recipient or not sender:
            return False

        message = EmailMessage()
        message["Subject"] = email.subject
        message["From"] = str(sender)
        message["To"] = email.recipient
        message["Date"] = formatdate(localtime=True)
        message.add_alternative(email.html_body, subtype="html")

        try:
            port = cast(int, settings["port"])
            if bool(settings["use_ssl"]):
                with smtplib.SMTP_SSL(str(server), port) as smtp:
                    _authenticate_and_send(smtp, settings, message)
            else:
                with smtplib.SMTP(str(server), port) as smtp:
                    if bool(settings["use_tls"]):
                        smtp.starttls()
                    _authenticate_and_send(smtp, settings, message)
        except Exception:
            current_app.logger.exception(email.error_message)
            return False
        return True


def _mail_settings() -> dict[str, object]:
    return {
        "server": current_app.config.get("MAIL_SERVER"),
        "port": current_app.config.get("MAIL_PORT", 587),
        "use_tls": bool(current_app.config.get("MAIL_USE_TLS", True)),
        "use_ssl": bool(current_app.config.get("MAIL_USE_SSL", False)),
        "username": current_app.config.get("MAIL_USERNAME"),
        "password": current_app.config.get("MAIL_PASSWORD"),
        "sender": current_app.config.get("MAIL_DEFAULT_SENDER"),
        "recipient": current_app.config.get("MODERATION_NOTIFICATION_EMAIL")
        or current_app.config.get("CREATOR_REQUEST_NOTIFICATION_EMAIL"),
    }


def send_creator_request_notification(user: User) -> bool:
    """Send a notification email when a creator request is submitted."""
    recipient = _mail_settings()["recipient"]
    if not recipient:
        return False
    subject = "[Recipe Site] Nieuwe creator-aanvraag"
    return EmailFactory.create(
        subject=subject,
        recipient=str(recipient),
        template="emails/creator_request.html",
        error_message="Failed to send creator-request notification email",
        heading="Nieuwe creator-aanvraag",
        subtitle="Sla op, deel en ontdek heerlijke recepten.",
        username=user.username,
        email=user.email,
        user_id=user.id,
        admin_url=_creator_requests_url(),
    ).send()


def send_password_reset_email(user: User, token: str) -> bool:
    """Send a reset link to its account owner without disclosing account data."""
    subject = "[Recepten] Herstel je wachtwoord"
    return EmailFactory.create(
        subject=subject,
        recipient=user.email,
        template="emails/password_reset.html",
        sender_fallback="username",
        error_message="Failed to send password-reset email",
        heading="Herstel je wachtwoord",
        subtitle=None,
        reset_url=url_for("auth.reset_password", token=token, _external=True),
        minutes=int(
            current_app.config.get("PASSWORD_RESET_TOKEN_LIFETIME_MINUTES", 60)
        ),
    ).send()


def send_recipe_moderation_notification(
    recipe: Recipe, moderation: ModerationResult
) -> bool:
    """Notify the configured recipient about a flagged recipe."""
    if not moderation.is_flagged:
        return False
    signature = _recipe_moderation_signature(recipe, moderation)
    if recipe.moderation_notification_signature == signature:
        return False
    recipient = _mail_settings()["recipient"]
    if not recipient:
        return False

    subject = f"[Recipe Site] Moderatieprobleem: {recipe.title}"
    sent = EmailFactory.create(
        subject=subject,
        recipient=str(recipient),
        template="emails/moderation.html",
        error_message="Failed to send recipe-moderation notification email",
        heading="Moderatieprobleem gevonden",
        subtitle=None,
        accent="#dc3545",
        title=recipe.title,
        author=recipe.author.username,
        recipe_id=recipe.id,
        status=recipe.status,
        issues=[issue.message for issue in moderation.issues],
        admin_url=_recipe_admin_url(),
    ).send()
    if not sent:
        return False

    recipe.moderation_notification_signature = signature
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to persist recipe moderation notification signature"
        )
        return False
    return True


def _creator_requests_url() -> str:
    return url_for("admin.users", _external=True)


def _recipe_admin_url() -> str:
    return url_for("admin.recipes", _external=True)


def _recipe_moderation_signature(recipe: Recipe, moderation: ModerationResult) -> str:
    digest = hashlib.sha256()
    digest.update(f"recipe:{recipe.id}|".encode())
    for issue in moderation.issues:
        digest.update(
            f"{issue.field}|{issue.category}|{issue.term}|{issue.message}".encode()
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _send_referenced_recipe_notification(
    *,
    recipe: Recipe,
    referenced_recipe: Recipe,
    subject: str,
    heading: str,
    notification_type: str,
    error_message: str,
    dependency_status: str | None = None,
) -> bool:
    if not recipe.author or not recipe.author.email:
        return False
    return EmailFactory.create(
        subject=subject,
        recipient=recipe.author.email,
        template="emails/recipe_reference.html",
        error_message=error_message,
        heading=heading,
        subtitle=None,
        notification_type=notification_type,
        dependency_status=dependency_status,
        owner=recipe.author.username,
        recipe_title=recipe.title,
        referenced_title=referenced_recipe.title,
        dependent_status=recipe.status,
    ).send()


def send_referenced_recipe_update_notification(
    recipe: Recipe, referenced_recipe: Recipe
) -> bool:
    """Notify owners when a nested referenced recipe was updated."""
    notification_type = (
        "unavailable" if referenced_recipe.status != Recipe.STATUS_PUBLIC else "updated"
    )
    heading = (
        "Recept niet meer beschikbaar"
        if notification_type == "unavailable"
        else "Recept aangepast"
    )
    subject = (
        f"[Recipe Site] Recept niet meer beschikbaar: {referenced_recipe.title}"
        if notification_type == "unavailable"
        else (
            "[Recipe Site] Recept waar je naar verwijst is aangepast: "
            f"{referenced_recipe.title}"
        )
    )
    return _send_referenced_recipe_notification(
        recipe=recipe,
        referenced_recipe=referenced_recipe,
        subject=subject,
        heading=heading,
        notification_type=notification_type,
        dependency_status=referenced_recipe.status,
        error_message="Failed to send referenced recipe update notification email",
    )


def send_referenced_recipe_deletion_notification(
    recipe: Recipe, deleted_recipe: Recipe
) -> bool:
    """Notify owners when a referenced recipe was deleted and their recipe was converted to concept."""
    return _send_referenced_recipe_notification(
        recipe=recipe,
        referenced_recipe=deleted_recipe,
        subject=f"[Recipe Site] Recept verwijderd: {deleted_recipe.title}",
        heading="Recept verwijderd",
        notification_type="unavailable",
        dependency_status="deleted",
        error_message="Failed to send referenced recipe deletion notification email",
    )


def _authenticate_and_send(
    smtp: smtplib.SMTP, settings: dict[str, object], message: EmailMessage
) -> None:
    username = settings["username"]
    password = settings["password"]
    if username and password:
        smtp.login(str(username), str(password))
    smtp.send_message(message)
