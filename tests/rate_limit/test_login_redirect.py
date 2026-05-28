"""
P1-7: login from_url must not be HTML-interpolated.

Lives in tests/rate_limit/ to inherit the DB-free conftest override — these
tests only exercise the auth endpoint at the HTTP layer.
"""

import inspect


def test_login_uses_redirect_response_not_html_meta_refresh():
    """The login handler must use RedirectResponse, never a meta-refresh HTML page."""
    from camp44.api.v1.endpoints import auth

    src = inspect.getsource(auth.login)
    assert "RedirectResponse" in src, "login() must use RedirectResponse"
    assert "meta http-equiv" not in src, (
        "login() must NOT use meta-refresh HTML "
        "(P1-7: HTML interpolation of redirect URL)"
    )
    assert "<html>" not in src, "login() must NOT inline HTML for redirect"
    assert "HTMLResponse(content=" not in src, (
        "login() must NOT wrap a string in HTMLResponse"
    )


def test_sanitize_rejects_evil_host_and_scheme():
    from camp44.api.v1.endpoints.auth import _sanitize_redirect_url

    assert _sanitize_redirect_url("https://evil.com/path") is None
    assert _sanitize_redirect_url("javascript:alert(1)") is None
    assert _sanitize_redirect_url(None) is None
    assert (
        _sanitize_redirect_url("https://app.scalemate.me/dashboard")
        == "https://app.scalemate.me/dashboard"
    )


def test_sanitize_rejects_html_injection_attempt():
    """A URL with a different host (even with HTML-injection chars) must be rejected."""
    from camp44.api.v1.endpoints.auth import _sanitize_redirect_url

    payload = 'https://attacker.com/x"><script>alert(1)</script>'
    assert _sanitize_redirect_url(payload) is None


def test_localhost_allowed_in_dev_blocked_in_prod(monkeypatch):
    """
    Codex P1-7 follow-up: ``localhost`` is a dev-only allowed redirect.

    A network-local attacker on the victim's machine could otherwise stand
    up a loopback listener and capture the post-login auth code.
    """
    from camp44.api.v1.endpoints import auth
    from camp44.api.v1.endpoints.auth import _sanitize_redirect_url

    # Force dev mode regardless of how settings was loaded by other tests.
    monkeypatch.setattr(auth, "_is_dev_environment", lambda: True)
    assert _sanitize_redirect_url("http://localhost:5173/") == "http://localhost:5173/"
    assert _sanitize_redirect_url("http://127.0.0.1:5173/") == "http://127.0.0.1:5173/"

    # Simulate a prod environment.
    monkeypatch.setattr(auth, "_is_dev_environment", lambda: False)
    assert _sanitize_redirect_url("http://localhost:5173/") is None
    assert _sanitize_redirect_url("http://127.0.0.1:5173/") is None
    # Production allowlist still works.
    assert (
        _sanitize_redirect_url("https://app.scalemate.me/dashboard")
        == "https://app.scalemate.me/dashboard"
    )
