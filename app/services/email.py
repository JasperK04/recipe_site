from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage
from email.utils import formatdate
import hashlib
from typing import cast

from flask import current_app, url_for

from app import db
from app.models import Recipe, User
from utils.moderation import ModerationResult


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
    """Send a notification email when a creator request is submitted.

    Returns True when an email was sent, False when notifications are disabled
    or required SMTP settings are missing.
    """
    settings = _mail_settings()
    server = settings["server"]
    recipient = settings["recipient"]
    sender = settings["sender"] or recipient
    admin_url = _creator_requests_url()

    if not server or not recipient or not sender:
        return False

    subject = "[Recipe Site] Nieuwe creator-aanvraag"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = str(sender)
    message["To"] = str(recipient)
    message["Date"] = formatdate(localtime=True)
    text_body = "\n".join(
        [
            "Er is een nieuwe creator-aanvraag ingediend.",
            "",
            f"Gebruikersnaam: {user.username}",
            f"E-mail: {user.email}",
            f"Gebruikers-ID: {user.id}",
            "",
            f"Open de beheerpagina: {admin_url}",
        ]
    )
    escaped_username = html.escape(user.username)
    escaped_email = html.escape(user.email)
    escaped_admin_url = html.escape(admin_url, quote=True)
    html_body = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f8f9fa;font-family:Arial,Helvetica,sans-serif;color:#212529;">
    <div style="max-width:680px;margin:0 auto;padding:32px 20px;">
      <div style="border:1px solid rgba(0,0,0,0.2);border-radius:8px;overflow:hidden;background:#ffffff;">
        <div style="background:#0d6efd;color:#ffffff;padding:22px 28px;">
          <div style="font-size:14px;letter-spacing:0.04em;text-transform:uppercase;font-weight:700;opacity:0.95;">
            Recepten
          </div>
          <div style="margin-top:8px;font-size:24px;line-height:1.2;font-weight:700;">
            Nieuwe creator-aanvraag
          </div>
          <div style="margin-top:8px;font-size:15px;line-height:1.5;opacity:0.95;">
            Sla op, deel en ontdek heerlijke recepten.
          </div>
        </div>
        <div style="padding:28px;">
          <p style="margin:0 0 18px;font-size:16px;line-height:1.6;">
            Er is een nieuwe creator-aanvraag ingediend. Hieronder staan de gegevens van de aanvrager.
          </p>
          <table style="width:100%;border-collapse:collapse;margin:0 0 24px;background:#f8f9fa;border-radius:6px;overflow:hidden;">
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid rgba(0,0,0,0.08);font-weight:700;width:160px;">Gebruikersnaam</td>
              <td style="padding:12px 16px;border-bottom:1px solid rgba(0,0,0,0.08);">{escaped_username}</td>
            </tr>
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid rgba(0,0,0,0.08);font-weight:700;">E-mail</td>
              <td style="padding:12px 16px;border-bottom:1px solid rgba(0,0,0,0.08);">{escaped_email}</td>
            </tr>
            <tr>
              <td style="padding:12px 16px;font-weight:700;">Gebruikers-ID</td>
              <td style="padding:12px 16px;">{user.id}</td>
            </tr>
          </table>
          <a href="{escaped_admin_url}" style="display:inline-block;background:#0d6efd;color:#ffffff;text-decoration:none;padding:12px 18px;border-radius:6px;font-weight:700;">
            Open gebruikersbeheer
          </a>
          <p style="margin:20px 0 0;font-size:13px;line-height:1.5;color:#6c757d;">
            Als de knop niet werkt, gebruik deze link: <a href="{escaped_admin_url}" style="color:#0d6efd;">{escaped_admin_url}</a>
          </p>
        </div>
        <div style="padding:16px 28px;background:#f8f9fa;border-top:1px solid rgba(0,0,0,0.08);font-size:12px;line-height:1.5;color:#6c757d;">
          Recepten • Een plek om je kookrecepten op te slaan en te delen.
        </div>
      </div>
    </div>
  </body>
</html>
"""
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

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
        current_app.logger.exception(
            "Failed to send creator-request notification email"
        )
        return False

    return True


def send_recipe_moderation_notification(
    recipe: Recipe, moderation: ModerationResult
) -> bool:
    """Notify the configured recipient about a flagged recipe."""
    if not moderation.is_flagged:
        return False

    signature = _recipe_moderation_signature(recipe, moderation)
    if recipe.moderation_notification_signature == signature:
        return False

    settings = _mail_settings()
    server = settings["server"]
    recipient = settings["recipient"]
    sender = settings["sender"] or recipient
    admin_url = _recipe_admin_url()

    if not server or not recipient or not sender:
        return False

    subject = f"[Recipe Site] Moderatieprobleem: {recipe.title}"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = str(sender)
    message["To"] = str(recipient)
    message["Date"] = formatdate(localtime=True)
    issue_lines = [f"- {issue.message}" for issue in moderation.issues]
    text_body = "\n".join(
        [
            "Er is een recept opgeslagen dat moderatie nodig heeft.",
            "",
            f"Titel: {recipe.title}",
            f"Auteur: {recipe.author.username}",
            f"Recept-ID: {recipe.id}",
            f"Status: {recipe.status}",
            "",
            "Gevonden problemen:",
            *issue_lines,
            "",
            f"Open de beheerpagina: {admin_url}",
        ]
    )
    escaped_title = html.escape(recipe.title)
    escaped_username = html.escape(recipe.author.username)
    escaped_admin_url = html.escape(admin_url, quote=True)
    escaped_status = html.escape(recipe.status)
    escaped_issue_items = "".join(
        f"<li>{html.escape(issue.message)}</li>" for issue in moderation.issues
    )
    html_body = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f8f9fa;font-family:Arial,Helvetica,sans-serif;color:#212529;">
    <div style="max-width:680px;margin:0 auto;padding:32px 20px;">
      <div style="border:1px solid rgba(0,0,0,0.2);border-radius:8px;overflow:hidden;background:#ffffff;">
        <div style="background:#dc3545;color:#ffffff;padding:22px 28px;">
          <div style="font-size:14px;letter-spacing:0.04em;text-transform:uppercase;font-weight:700;opacity:0.95;">
            Recepten
          </div>
          <div style="margin-top:8px;font-size:24px;line-height:1.2;font-weight:700;">
            Moderatieprobleem gevonden
          </div>
        </div>
        <div style="padding:28px;">
          <p style="margin:0 0 18px;font-size:16px;line-height:1.6;">
            Een recept is gemarkeerd tijdens moderatie. Hieronder staan de details en alle gevonden problemen.
          </p>
          <table style="width:100%;border-collapse:collapse;margin:0 0 24px;background:#f8f9fa;border-radius:6px;overflow:hidden;">
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid rgba(0,0,0,0.08);font-weight:700;width:160px;">Titel</td>
              <td style="padding:12px 16px;border-bottom:1px solid rgba(0,0,0,0.08);">{escaped_title}</td>
            </tr>
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid rgba(0,0,0,0.08);font-weight:700;">Auteur</td>
              <td style="padding:12px 16px;border-bottom:1px solid rgba(0,0,0,0.08);">{escaped_username}</td>
            </tr>
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid rgba(0,0,0,0.08);font-weight:700;">Recept-ID</td>
              <td style="padding:12px 16px;border-bottom:1px solid rgba(0,0,0,0.08);">{recipe.id}</td>
            </tr>
            <tr>
              <td style="padding:12px 16px;font-weight:700;">Status</td>
              <td style="padding:12px 16px;">{escaped_status}</td>
            </tr>
          </table>
          <div style="margin:0 0 18px;font-weight:700;">Gevonden problemen</div>
          <ul style="margin:0 0 24px;padding-left:22px;line-height:1.6;">
            {escaped_issue_items}
          </ul>
          <a href="{escaped_admin_url}" style="display:inline-block;background:#0d6efd;color:#ffffff;text-decoration:none;padding:12px 18px;border-radius:6px;font-weight:700;">
            Open receptmoderatie
          </a>
        </div>
      </div>
    </div>
  </body>
</html>
"""
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

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
        current_app.logger.exception(
            "Failed to send recipe-moderation notification email"
        )
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


def _recipe_moderation_signature(
    recipe: Recipe, moderation: ModerationResult
) -> str:
    digest = hashlib.sha256()
    digest.update(f"recipe:{recipe.id}|".encode("utf-8"))
    for issue in moderation.issues:
        digest.update(
            "|".join(
                [issue.field, issue.category, issue.term, issue.message]
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _authenticate_and_send(
    smtp: smtplib.SMTP, settings: dict[str, object], message: EmailMessage
) -> None:
    username = settings["username"]
    password = settings["password"]
    if username and password:
        smtp.login(str(username), str(password))
    smtp.send_message(message)
