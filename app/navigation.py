"""Helpers for safe, context-aware navigation within the application."""

from urllib.parse import unquote, urlsplit, urlunsplit

from flask import g, request, session, url_for


def _safe_internal_target(target: str | None) -> str | None:
    """Return a relative in-app redirect target, or ``None`` if it is unsafe."""
    if not target:
        return None

    parsed = urlsplit(target)
    decoded_target = unquote(target)
    if (
        parsed.scheme
        or parsed.netloc
        or not parsed.path.startswith("/")
        or decoded_target.startswith(("//", "/\\"))
    ):
        return None
    return target


def safe_redirect_target(target: str | None) -> str | None:
    """Validate a user-supplied redirect target before redirecting to it."""
    return _safe_internal_target(target)


def safe_referrer_url() -> str | None:
    """Return the path and query string of a same-origin Referer header."""
    referrer = request.referrer
    if not referrer:
        return None

    parsed = urlsplit(referrer)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.netloc != request.host
        or not parsed.path.startswith("/")
        # Returning to login after it redirects to the protected page is not a
        # useful Back destination and can send visitors through a login loop.
        or parsed.path == "/account/inloggen"
    ):
        return None

    return _safe_internal_target(urlunsplit(("", "", parsed.path, parsed.query, "")))


def back_url(fallback_endpoint: str, **fallback_values: object) -> str:
    """Get the originating in-app URL, falling back to a named endpoint.

    A pending referrer is saved when Flask-Login sends a visitor to the login
    page.  That keeps a protected page's Back control useful after login.
    """
    pending_back_url = getattr(g, "pending_back_url", None)
    return (
        pending_back_url
        or safe_referrer_url()
        or url_for(fallback_endpoint, **fallback_values)
    )


def remember_back_url_for_login() -> None:
    """Save the page preceding a protected request through the login flow."""
    back = safe_referrer_url()
    if back:
        session["post_login_back_url"] = back


def load_pending_back_url() -> None:
    """Make a login-flow referrer available to the first rendered destination."""
    if request.endpoint != "auth.login":
        g.pending_back_url = session.pop("post_login_back_url", None)
