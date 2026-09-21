from pathlib import Path

import pytest

from app import create_app, db
from app.models import AnalyticsEvent, User
from app.services.recipe_import import (
    PENDING_RECIPE_IMAGE_TOKEN_SESSION_KEY,
    pending_recipe_image_path,
)
from config import DevelopmentConfig, config


class RecipeImportTestConfig(DevelopmentConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"


@pytest.fixture()
def app(monkeypatch, tmp_path):
    monkeypatch.setitem(config, "recipe_import_test", RecipeImportTestConfig)
    application = create_app("recipe_import_test")
    application.config["DATA_ROOT"] = tmp_path
    (tmp_path / "recipe_import").mkdir()
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def test_pending_import_image_can_be_requested_more_than_once(app):
    with app.app_context():
        user = User(username="import-user", email="import-user@example.test")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        token = "8459b48f941b4e66adad3c3c288ec126"
        image_path = pending_recipe_image_path(token)
        image_path.write_bytes(b"image-data")

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
        session[PENDING_RECIPE_IMAGE_TOKEN_SESSION_KEY] = token

    first = client.get(f"/recept/importafbeelding/{token}")
    second = client.get(f"/recept/importafbeelding/{token}")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.data == b"image-data"
    assert second.data == b"image-data"
    assert Path(image_path).is_file()


def test_missing_pending_import_image_is_not_logged_as_application_error(app):
    with app.app_context():
        user = User(username="missing-image-user", email="missing-image@example.test")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        token = "missing-image-token"

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
        session[PENDING_RECIPE_IMAGE_TOKEN_SESSION_KEY] = token

    response = client.get(f"/recept/importafbeelding/{token}")

    assert response.status_code == 404
    with app.app_context():
        assert AnalyticsEvent.query.filter_by(event_type="error").count() == 0
