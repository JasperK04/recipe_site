from flask import Flask, redirect

from app.navigation import back_url, safe_redirect_target, safe_referrer_url


def _navigation_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"

    @app.route("/fallback")
    def fallback():
        return "fallback"

    @app.route("/back")
    def back():
        return redirect(back_url("fallback"))

    @app.route("/account/inloggen")
    def login():
        return "login"

    return app


def test_back_url_preserves_same_origin_path_and_query():
    client = _navigation_app().test_client()

    response = client.get(
        "/back",
        headers={"Referer": "http://localhost/recipe/?category=lunch&page=3"},
    )

    assert response.location == "/recipe/?category=lunch&page=3"


def test_back_url_rejects_external_referrer_and_uses_fallback():
    client = _navigation_app().test_client()

    response = client.get("/back", headers={"Referer": "https://evil.example/path"})

    assert response.location == "/fallback"


def test_back_url_does_not_return_to_login_after_authentication():
    client = _navigation_app().test_client()

    response = client.get(
        "/back", headers={"Referer": "http://localhost/account/inloggen"}
    )

    assert response.location == "/fallback"


def test_safe_redirect_target_rejects_external_and_protocol_relative_urls():
    assert (
        safe_redirect_target("/recipe/123?source=search") == "/recipe/123?source=search"
    )
    assert safe_redirect_target("https://evil.example") is None
    assert safe_redirect_target("//evil.example") is None
    assert safe_redirect_target("/%2f%2fevil.example") is None


def test_safe_referrer_url_rejects_a_different_host():
    app = _navigation_app()
    with app.test_request_context(
        "/back", headers={"Referer": "http://other.example/recipe/?page=3"}
    ):
        assert safe_referrer_url() is None
