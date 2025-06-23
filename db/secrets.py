from __future__ import annotations

"""Minimal helper for fetching secrets from AWS Secrets Manager.

This keeps the app code independent of the underlying secret-store; in local
or CI runs the helper falls back to plain environment variables so the rest of
the codebase continues to work without AWS credentials.
"""

import functools
import json
import os
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError


@functools.lru_cache(maxsize=128)
def _fetch_secret_raw(secret_id: str) -> Optional[str]:
    """Return the *raw* secret string from Secrets Manager.

    Falls back to `os.getenv(secret_id)` when AWS is not configured (e.g. local
    dev, CI).
    """
    # Local / test fallback -----------------------------------------------
    fallback = os.getenv(secret_id)
    if "AWS_REGION" not in os.environ and fallback is not None:
        return fallback

    # Attempt real Secrets Manager lookup ----------------------------------
    try:
        client = boto3.client("secretsmanager")
        resp: Dict[str, Any] = client.get_secret_value(SecretId=secret_id)
    except (BotoCoreError, ClientError):
        # Hard-fail is not desirable in dev; return env or None
        return fallback

    return resp.get("SecretString") or fallback


def get_secret(secret_id: str, *, parse_json: bool = False) -> Any:
    """Public API for callers.

    Example::
        db_creds = get_secret("camp44/rds", parse_json=True)
        jwt_key = get_secret("camp44/jwt_secret")
    """
    raw = _fetch_secret_raw(secret_id)
    if raw is None:
        raise RuntimeError(f"Secret '{secret_id}' not found in env or Secrets Manager")

    if parse_json:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Secret '{secret_id}' is not valid JSON") from exc
    return raw
