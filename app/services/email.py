from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage
from email.utils import formatdate
from typing import cast

from flask import current_app, url_for

from app.models import User


def _mail_settings() -> dict[str, object]:
    return {
        "server": current_app.config.get("MAIL_SERVER"),
        "port": current_app.config.get("MAIL_PORT", 587),
        "use_tls": bool(current_app.config.get("MAIL_USE_TLS", True)),
        "use_ssl": bool(current_app.config.get("MAIL_USE_SSL", False)),
        "username": current_app.config.get("MAIL_USERNAME"),
        "password": current_app.config.get("MAIL_PASSWORD"),
        "sender": current_app.config.get("MAIL_DEFAULT_SENDER"),
        "recipient": current_app.config.get("CREATOR_REQUEST_NOTIFICATION_EMAIL"),
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


def _creator_requests_url() -> str:
    return url_for("admin.users", _external=True)


def _authenticate_and_send(
    smtp: smtplib.SMTP, settings: dict[str, object], message: EmailMessage
) -> None:
    username = settings["username"]
    password = settings["password"]
    if username and password:
        smtp.login(str(username), str(password))
    smtp.send_message(message)
