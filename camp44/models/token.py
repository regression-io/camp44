from typing import Optional

from sqlmodel import SQLModel


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    expires_in: int = 900  # seconds (15 min default)


class TokenPayload(SQLModel):
    sub: str
    tv: int = 0  # token_version — defaults to 0 for backward compat
