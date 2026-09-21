from dataclasses import dataclass

import pytest

from app import create_app, db
from app.models import Recipe, User
from app.services.email import (
    EmailFactory,
    send_creator_request_notification,
    send_password_reset_email,
    send_recipe_moderation_notification,
    send_referenced_recipe_deletion_notification,
    send_referenced_recipe_update_notification,
)
from config import DevelopmentConfig, config
from utils.moderation import ModerationIssue, ModerationResult


class EmailTestConfig(DevelopmentConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    MAIL_SERVER = "smtp.example.test"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = "mailer@example.test"
    MAIL_PASSWORD = "secret"
    MAIL_DEFAULT_SENDER = "mailer@example.test"
    MODERATION_NOTIFICATION_EMAIL = "admin@example.test"


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setitem(config, "email_test", EmailTestConfig)
    application = create_app("email_test")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@dataclass
class FakeSMTP:
    server: str
    port: int
    messages: list
    tls_started: bool = False
    logged_in: bool = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self):
        self.tls_started = True

    def login(self, _username, _password):
        self.logged_in = True

    def send_message(self, message):
        self.messages.append(message)


def test_factory_owns_headers_tls_authentication_and_delivery(app, monkeypatch):
    smtp_instances = []
    messages = []

    def smtp_factory(server, port):
        smtp = FakeSMTP(server, port, messages)
        smtp_instances.append(smtp)
        return smtp

    monkeypatch.setattr("app.services.email.smtplib.SMTP", smtp_factory)

    with app.app_context():
        sent = EmailFactory.create(
            subject="Subject",
            recipient="person@example.test",
            template="emails/password_reset.html",
            heading="Subject",
            subtitle=None,
            reset_url="https://example.test/reset",
            minutes=60,
        ).send()

    assert sent is True
    assert len(messages) == 1
    assert messages[0]["Subject"] == "Subject"
    assert messages[0]["From"] == "mailer@example.test"
    assert messages[0]["To"] == "person@example.test"
    assert (
        messages[0].get_body(preferencelist=("html",)).get_content_type() == "text/html"
    )
    assert messages[0].get_body(preferencelist=("plain",)) is None
    assert smtp_instances[0].tls_started is True
    assert smtp_instances[0].logged_in is True


def test_factory_returns_false_when_mail_is_not_configured(app, monkeypatch):
    monkeypatch.setitem(app.config, "MAIL_SERVER", None)
    smtp_called = False

    def smtp_factory(*_args):
        nonlocal smtp_called
        smtp_called = True
        raise AssertionError("SMTP should not be opened")

    monkeypatch.setattr("app.services.email.smtplib.SMTP", smtp_factory)

    with app.app_context():
        sent = EmailFactory.create(
            subject="Subject",
            recipient="person@example.test",
            template="emails/password_reset.html",
            heading="Subject",
            subtitle=None,
            reset_url="https://example.test/reset",
            minutes=60,
        ).send()

    assert sent is False
    assert smtp_called is False


def test_supported_email_types_use_central_sender(app, monkeypatch):
    messages = []

    def smtp_factory(_server, _port):
        return FakeSMTP("smtp.example.test", 587, messages)

    monkeypatch.setattr("app.services.email.smtplib.SMTP", smtp_factory)
    user = User(username="chef", email="chef@example.test")
    author = User(username="author", email="author@example.test")
    recipe = Recipe(
        id=7,
        title="Pasta",
        ingredients=["pasta"],
        instructions=["Cook"],
        status=Recipe.STATUS_PUBLIC,
        author=author,
    )
    issue = ModerationIssue(
        field="title", category="term", term="bad", message="Controleer de titel"
    )
    moderation = ModerationResult(status="flagged", issues=[issue])

    with app.test_request_context():
        assert send_creator_request_notification(user) is True
        assert send_password_reset_email(user, "token") is True
        assert send_recipe_moderation_notification(recipe, moderation) is True
        assert send_referenced_recipe_update_notification(recipe, recipe) is True
        assert send_referenced_recipe_deletion_notification(recipe, recipe) is True

    assert len(messages) == 5
    assert messages[0]["To"] == "admin@example.test"
    assert messages[1]["To"] == "chef@example.test"
    assert messages[2]["Subject"].startswith("[Recipe Site] Moderatieprobleem:")
    assert messages[3]["To"] == "author@example.test"
    assert messages[4]["To"] == "author@example.test"


def test_dependency_unavailable_email_explains_private_and_deactivated_states(
    app, monkeypatch
):
    messages = []
    monkeypatch.setattr(
        "app.services.email.smtplib.SMTP",
        lambda _server, _port: FakeSMTP("smtp.example.test", 587, messages),
    )
    author = User(username="author", email="author@example.test")
    dependent = Recipe(
        title="Pasta",
        ingredients=["pasta"],
        instructions=["Cook"],
        status=Recipe.STATUS_PRIVATE,
        author=author,
    )
    private_dependency = Recipe(
        title="Private saus",
        ingredients=["tomaat"],
        instructions=["Cook"],
        status=Recipe.STATUS_PRIVATE,
        author=author,
    )
    deactivated_dependency = Recipe(
        title="Gedeactiveerde saus",
        ingredients=["tomaat"],
        instructions=["Cook"],
        status=Recipe.STATUS_DEACTIVATED,
        author=author,
    )

    with app.test_request_context():
        assert (
            send_referenced_recipe_update_notification(dependent, private_dependency)
            is True
        )
        assert (
            send_referenced_recipe_update_notification(
                dependent, deactivated_dependency
            )
            is True
        )

    assert messages[0]["Subject"].startswith(
        "[Recipe Site] Recept niet meer beschikbaar:"
    )
    private_html = messages[0].get_body(preferencelist=("html",)).get_content()
    deactivated_html = messages[1].get_body(preferencelist=("html",)).get_content()
    assert "privé gemaakt" in private_html
    assert "gedeactiveerd" in deactivated_html
    assert private_html.count("automatisch privé gemaakt") == 1
    assert deactivated_html.count("automatisch privé gemaakt") == 1


def test_moderation_notification_is_sent_only_once_for_same_signature(app, monkeypatch):
    messages = []
    monkeypatch.setattr(
        "app.services.email.smtplib.SMTP",
        lambda _server, _port: FakeSMTP("smtp.example.test", 587, messages),
    )
    with app.app_context():
        author = User(username="author", email="author@example.test")
        db.session.add(author)
        db.session.flush()
        recipe = Recipe(
            title="Pasta",
            ingredients=["pasta"],
            instructions=["Cook"],
            status=Recipe.STATUS_PUBLIC,
            user_id=author.id,
        )
        db.session.add(recipe)
        db.session.commit()
        moderation = ModerationResult(
            status="flagged",
            issues=[
                ModerationIssue(
                    field="title",
                    category="term",
                    term="bad",
                    message="Controleer de titel",
                )
            ],
        )

        assert send_recipe_moderation_notification(recipe, moderation) is True
        assert send_recipe_moderation_notification(recipe, moderation) is False

    assert len(messages) == 1
