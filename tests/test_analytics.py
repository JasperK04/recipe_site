from datetime import UTC, datetime

import pytest

from app import create_app, db
from app.models import AnalyticsErrorGroup, AnalyticsEvent, Recipe, User
from app.services.analytics import Analytics
from config import DevelopmentConfig, config


class AnalyticsTestConfig(DevelopmentConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    ANALYTICS_ERROR_BUCKET_MINUTES = 15


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setitem(config, "analytics_test", AnalyticsTestConfig)
    application = create_app("analytics_test")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _create_user(*, admin=False):
    user = User(
        username="analytics-admin" if admin else "analytics-user",
        email=(
            "analytics-admin@example.test" if admin else "analytics-user@example.test"
        ),
        role=User.ROLE_CHEF_DE_CUISINE if admin else User.ROLE_FIJNPROEVER,
    )
    user.set_password("password")
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def test_public_route_records_pageview_request_and_reuses_visitor(client, app):
    first = client.get("/")
    second = client.get("/")

    assert first.status_code == 200
    assert second.status_code == 200
    with app.app_context():
        pageviews = AnalyticsEvent.query.filter_by(event_type="page_view").all()
        requests = AnalyticsEvent.query.filter_by(event_type="request").all()
        assert len(pageviews) == 2
        assert len(requests) == 2
        assert len({event.visitor_id for event in pageviews}) == 1
        assert len({event.visitor_id for event in requests}) == 1


def test_public_recipe_route_records_recipe_view(client, app):
    with app.app_context():
        author = _create_user()
        recipe = Recipe(
            title="Analytics recept",
            ingredients=[],
            instructions=[],
            status=Recipe.STATUS_PUBLIC,
            user_id=author.id,
        )
        db.session.add(recipe)
        db.session.commit()
        recipe_url = f"/recept/{recipe.id}/{recipe.url_title}"

    response = client.get(recipe_url)

    assert response.status_code == 200
    with app.app_context():
        event = AnalyticsEvent.query.filter_by(event_type="recipe_view").one()
        assert event.recipe_id == recipe.id
        assert event.path == recipe_url
        assert event.status_code == 200


def test_not_found_route_records_error_without_pageview(client, app):
    response = client.get("/missing-analytics-page")

    assert response.status_code == 404
    with app.app_context():
        assert (
            AnalyticsEvent.query.filter_by(event_type="error").one().status_code == 404
        )
        assert AnalyticsEvent.query.filter_by(event_type="page_view").count() == 0


def test_identical_errors_merge_inside_fixed_quarter_hour_bucket(app):
    with app.app_context():
        signature = {
            "status_code": 404,
            "path": "/recept/302/afbeelding",
            "method": "GET",
            "error_type": "NotFound",
            "referrer": "http://example.test/",
        }
        for occurred_at in (
            datetime(2026, 9, 21, 7, 0, tzinfo=UTC),
            datetime(2026, 9, 21, 7, 14, 59, tzinfo=UTC),
            datetime(2026, 9, 21, 7, 15, tzinfo=UTC),
        ):
            Analytics._record_error_group(occurred_at=occurred_at, **signature)
            db.session.commit()

        groups = AnalyticsErrorGroup.query.order_by(
            AnalyticsErrorGroup.bucket_started_at
        ).all()
        assert [group.occurrence_count for group in groups] == [2, 1]
        assert [group.bucket_started_at.minute for group in groups] == [0, 15]


def test_admin_analytics_route_is_available_to_admin(client, app):
    with app.app_context():
        admin = _create_user(admin=True)
        admin_id = admin.id
    _login(client, admin)

    response = client.get("/admin/analytics")

    assert response.status_code == 200
    assert "Recente fouten" in response.get_data(as_text=True)
    with app.app_context():
        assert AnalyticsEvent.query.filter_by(path="/admin/analytics").count() == 1
        assert db.session.get(User, admin_id) is not None


def test_error_referrer_exposes_only_a_clickable_internal_path(app):
    with app.app_context():
        error = AnalyticsErrorGroup(
            first_occurred_at=datetime.now(UTC),
            last_occurred_at=datetime.now(UTC),
            occurrence_count=1,
            status_code=404,
            path="/missing",
            method="GET",
            referrer="http://172.18.118.252:5000/recept/toevoegen?source=upload",
        )

        assert error.referrer_path == "/recept/toevoegen?source=upload"
