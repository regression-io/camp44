"""
Rate limiting for auth surfaces.

Uses slowapi with in-memory storage (single-replica deploys). The limiter is
disabled when ``TESTING=1`` to avoid polluting the test suite; dedicated tests
opt in by toggling ``app.state.limiter.enabled = True``.

Keys are IP-only. Composite IP+email keys were considered but deferred — see
``scalemate-service/docs/bugs/P1-4/diagnosis.md``.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from camp44.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=not settings.TESTING,
    headers_enabled=True,
)
