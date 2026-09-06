import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from app import create_app, db
from app.api.users import PASSWORD_RESET_PURPOSE
from app.models import Credential, User
from config import DevelopmentConfig, config


class RecoveryTestConfig(DevelopmentConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    PASSWORD_RESET_TOKEN_LIFETIME_MINUTES = 10


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setitem(config, "recovery_test", RecoveryTestConfig)
    application = create_app("recovery_test")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def user(app):
    with app.app_context():
        account = User(username="chef", email="chef@example.test")
        account.set_password("old-password")
        db.session.add(account)
        db.session.commit()
        return account.id


def _request_reset(client, identifier, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.services.email.send_password_reset_email",
        lambda account, token: sent.append((account.id, token)) or True,
    )
    response = client.post("/api/password-reset/request", json={"identifier": identifier})
    return response, sent


def test_reset_request_is_enumeration_safe_and_accepts_username_or_email(
    app, client, user, monkeypatch
):
    existing, sent = _request_reset(client, "chef@example.test", monkeypatch)
    unknown, no_email = _request_reset(client, "missing-account", monkeypatch)

    assert existing.status_code == unknown.status_code == 200
    assert existing.get_json() == unknown.get_json()
    assert len(sent) == 1
    assert no_email == []

    response, sent = _request_reset(client, "chef", monkeypatch)
    assert response.status_code == 200
    assert len(sent) == 1
    with app.app_context():
        credential = Credential.query.filter_by(purpose=PASSWORD_RESET_PURPOSE).order_by(
            Credential.created_at.desc()
        ).first()
        assert credential.subject_id == user
        assert credential.secret_hash != sent[0][1]
        assert credential.used_at is None
        assert credential.max_uses == 1


def test_reset_verification_and_completion_are_single_use(app, client, user, monkeypatch):
    _, sent = _request_reset(client, "chef", monkeypatch)
    token = sent[0][1]

    assert client.post("/api/password-reset/verify", json={"token": token}).get_json() == {"valid": True}
    complete = client.post(
        "/api/password-reset/complete",
        json={"token": token, "newPassword": "new-password", "confirmPassword": "new-password"},
    )
    assert complete.status_code == 200
    assert client.post("/api/password-reset/verify", json={"token": token}).get_json() == {"valid": False}
    assert client.post(
        "/api/password-reset/complete",
        json={"token": token, "newPassword": "another-password", "confirmPassword": "another-password"},
    ).status_code == 400
    with app.app_context():
        refreshed = db.session.get(User, user)
        assert refreshed.check_password("new-password")
        assert refreshed.password_hash != "new-password"


def test_expired_and_wrong_purpose_tokens_cannot_reset(app, client, user):
    expired_token = "expired-token"
    invitation_token = "invitation-token"
    with app.app_context():
        db.session.add_all(
            [
                Credential(
                    purpose=PASSWORD_RESET_PURPOSE,
                    secret_hash=hashlib.sha256(expired_token.encode()).hexdigest(),
                    subject_type="user",
                    subject_id=user,
                    expires_at=datetime.now(UTC) - timedelta(minutes=1),
                ),
                Credential(
                    purpose="email_verification",
                    secret_hash=hashlib.sha256(invitation_token.encode()).hexdigest(),
                    subject_type="user",
                    subject_id=user,
                    expires_at=datetime.now(UTC) + timedelta(minutes=30),
                ),
            ]
        )
        db.session.commit()

    for token in (expired_token, invitation_token, "not-a-token"):
        assert client.post("/api/password-reset/verify", json={"token": token}).get_json() == {"valid": False}
        assert client.post(
            "/api/password-reset/complete",
            json={"token": token, "newPassword": "new-password", "confirmPassword": "new-password"},
        ).status_code == 400


def test_reset_rejects_bad_password_and_does_not_consume_token(app, client, user, monkeypatch):
    _, sent = _request_reset(client, "chef", monkeypatch)
    token = sent[0][1]
    mismatch = client.post(
        "/api/password-reset/complete",
        json={"token": token, "newPassword": "new-password", "confirmPassword": "different"},
    )
    short = client.post(
        "/api/password-reset/complete",
        json={"token": token, "newPassword": "short", "confirmPassword": "short"},
    )
    assert mismatch.status_code == short.status_code == 400
    assert client.post("/api/password-reset/verify", json={"token": token}).get_json() == {"valid": True}


def test_login_accepts_email_in_the_username_field(client, user):
    response = client.post(
        "/auth/login",
        data={"username": "chef@example.test", "password": "old-password"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_reset_page_shows_email_without_token_field(client, user, monkeypatch):
    _, sent = _request_reset(client, "chef", monkeypatch)
    response = client.get(f"/auth/reset-password?token={sent[0][1]}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'value="chef@example.test"' in html
    assert 'name="token"' not in html
    assert sent[0][1] not in html


def test_reset_page_uses_server_side_credential_on_post(client, user, monkeypatch):
    _, sent = _request_reset(client, "chef", monkeypatch)
    client.get(f"/auth/reset-password?token={sent[0][1]}")

    response = client.post(
        "/auth/reset-password",
        data={"new_password": "new-password", "confirm_password": "new-password"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")
