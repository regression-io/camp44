"""
Rate limiting for auth surfaces.

Storage: ``settings.REDIS_URL`` when set (shared across uvicorn workers /
replicas so limits are correct under multiple workers), otherwise in-memory
(per-process — fine for a single worker). ``swallow_errors`` makes the limiter
**fail open** if the storage backend is unreachable (a Redis outage must not
lock everyone out of auth). The limiter is disabled when ``TESTING=1`` to avoid
polluting the test suite; dedicated tests opt in by toggling
``app.state.limiter.enabled = True``.

Keys are IP-only. Composite IP+email keys were considered but deferred — see
``scalemate-service/docs/bugs/P1-4/diagnosis.md``.

``headers_enabled`` is OFF: slowapi's ``X-RateLimit-*`` header injection requires
each decorated route to expose a ``response: Response`` parameter (or return a
``Response``). Our sync handlers return Pydantic models (e.g. ``POST /auth/login``
returns ``Token``), so with header injection on, slowapi raised
``parameter 'response' must be an instance of starlette.responses.Response`` on
the *success* path — turning every successful password login into a 500 while
invalid-credential calls (which 401 earlier) looked fine. See the regression
test ``tests/rate_limit/test_limiter_no_500_on_success.py``. To re-enable rate
headers later, add a ``response: Response`` param to every ``@limiter.limit``
handler first.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from camp44.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=not settings.TESTING,
    headers_enabled=False,
    storage_uri=settings.REDIS_URL or "memory://",
    swallow_errors=True,
)
