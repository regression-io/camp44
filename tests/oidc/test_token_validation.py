"""
Contract tests for ``OIDCTokenValidator.validate_token``.

These lock the externally-observable behavior of OIDC bearer-token validation so
the ``authlib.jose`` → ``joserfc`` migration is provably behavior-preserving:

- a valid RS256 token with the expected ``iss``/``aud`` returns its claims;
- wrong ``aud``, wrong ``iss``, an expired token, an ``HS256`` token, and a
  garbage token all return ``None`` (never raise);
- the returned claims behave like a dict (``in`` / ``.get()``), which is all the
  ``tenant_oidc`` middleware relies on.

Tokens are minted with ``joserfc`` (standard RS256/JWKS), independent of whichever
library does the validating, so the same suite is green before and after the swap.
"""

import asyncio
import time

import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey

from camp44.core.config import settings
from camp44.core.oauth import OIDCTokenValidator

ISSUER = "https://idp.example.test"
AUDIENCE = "camp44-client-id"

_KEY = RSAKey.generate_key(2048, parameters={"kid": "test-key-1"})
_PUBLIC_JWKS = {"keys": [_KEY.as_dict(private=False)]}


def _mint(
    claims: dict, *, key: RSAKey = _KEY, alg: str = "RS256", kid: str = "test-key-1"
) -> str:
    header = {"alg": alg}
    if kid is not None:
        header["kid"] = kid
    return jwt.encode(header, claims, key)


@pytest.fixture(autouse=True)
def _oidc_settings():
    """Enable OIDC and point validation at our test issuer/audience + JWKS cache."""
    saved = {
        k: getattr(settings, k)
        for k in ("OAUTH_ENABLED", "OIDC_ISSUER_URL", "OIDC_CLIENT_ID", "OIDC_JWKS_URI")
    }
    settings.OAUTH_ENABLED = True
    settings.OIDC_ISSUER_URL = ISSUER
    settings.OIDC_CLIENT_ID = AUDIENCE
    settings.OIDC_JWKS_URI = f"{ISSUER}/jwks"
    # Pre-seed the class JWKS cache so get_jwks() never makes a network call.
    OIDCTokenValidator._jwks = _PUBLIC_JWKS
    yield
    for k, v in saved.items():
        setattr(settings, k, v)
    OIDCTokenValidator._jwks = None


def _validate(token: str):
    return asyncio.run(OIDCTokenValidator.validate_token(token))


def _valid_claims(**overrides) -> dict:
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-123",
        "exp": int(time.time()) + 3600,
        "tenant_id": "tenant-abc",
    }
    claims.update(overrides)
    return claims


def test_valid_token_returns_claims():
    """A valid RS256 token with the expected iss/aud returns its claims."""
    claims = _validate(_mint(_valid_claims()))
    assert claims is not None
    assert claims["sub"] == "user-123"
    # The tenant_oidc middleware uses `claim in claims` and `claims.get(...)`.
    assert "tenant_id" in claims
    assert claims.get("tenant_id") == "tenant-abc"


def test_wrong_audience_returns_none():
    """A token minted for a different audience is rejected."""
    assert _validate(_mint(_valid_claims(aud="someone-else"))) is None


def test_wrong_issuer_returns_none():
    """A token from an unexpected issuer is rejected."""
    assert _validate(_mint(_valid_claims(iss="https://evil.example"))) is None


def test_expired_token_returns_none():
    """An expired token is rejected."""
    assert _validate(_mint(_valid_claims(exp=int(time.time()) - 10))) is None


def test_hs256_token_returns_none():
    """An HS256 (Camp44) token must be rejected, not validated as RS256."""
    from joserfc.jwk import OctKey

    hs = jwt.encode(
        {"alg": "HS256"},
        _valid_claims(),
        OctKey.import_key("symmetric-secret-key-at-least-32-bytes!"),
    )
    assert _validate(hs) is None


def test_garbage_token_returns_none():
    """A non-JWT string is rejected without raising."""
    assert _validate("not-a-jwt") is None


def test_returns_none_when_oauth_disabled():
    """Validation short-circuits to None when OAuth is disabled."""
    settings.OAUTH_ENABLED = False
    assert _validate(_mint(_valid_claims())) is None
