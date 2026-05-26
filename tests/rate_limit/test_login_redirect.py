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
