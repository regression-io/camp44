"""
Regression for the login-500 bug (stress-test finding F1).

A ``@limiter.limit`` decorated *sync* endpoint that returns a normal value
(e.g. a Pydantic model, like ``POST /auth/login`` returning ``Token``) must not
raise on the success path. With ``headers_enabled=True`` and no ``response:
Response`` parameter, slowapi's ``_inject_headers`` raised
``parameter 'response' must be an instance of starlette.responses.Response``
*after* the handler succeeded — surfacing as a 500. Invalid-credential calls
short-circuit with a 401 before that point, which is why the existing
wrong-password rate-limit tests never caught it.

This reproduces the mechanism without a database: a decorated sync route that
returns a dict must return 200 when the limiter is enabled.
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from camp44.core.rate_limit import limiter


def _app() -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter

    @app.get("/decorated")
    @limiter.limit("100/minute")
    def decorated(request: Request):  # noqa: D401 - mirrors prod sync handlers
        # Returns a plain value (not a starlette Response), exactly like the
        # real auth handlers that return Pydantic models.
        return {"ok": True}

    return app


def test_limited_sync_endpoint_succeeds_when_enabled():
    """A limiter-decorated sync route returning a model must not 500 (F1)."""
    limiter.reset()
    limiter.enabled = True
    try:
        client = TestClient(_app(), raise_server_exceptions=False)
        resp = client.get("/decorated")
        assert resp.status_code == 200, (
            f"limiter-decorated success path returned {resp.status_code} "
            f"(login-500 regression): {resp.text}"
        )
        assert resp.json() == {"ok": True}
    finally:
        limiter.enabled = False
        limiter.reset()
