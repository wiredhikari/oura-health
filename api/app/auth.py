"""Single-user passcode → JWT auth.

Flow:
  POST /auth/login   { "passcode": "..." }   → { "token": "..." }
  Subsequent requests:  Authorization: Bearer <token>

The passcode lives in env (APP_PASSCODE). One user, no DB row needed.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import settings


SUBJECT = "single-user"
ALGO = "HS256"

_bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    passcode: str


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime


def mint_token() -> LoginResponse:
    s = settings()
    exp = datetime.now(timezone.utc) + timedelta(days=s.jwt_ttl_days)
    payload = {"sub": SUBJECT, "exp": exp}
    token = jwt.encode(payload, s.jwt_secret, algorithm=ALGO)
    return LoginResponse(token=token, expires_at=exp)


def require_auth(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    """FastAPI dependency. Raises 401 unless a valid bearer token is present."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    try:
        payload = jwt.decode(
            creds.credentials, settings().jwt_secret, algorithms=[ALGO]
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {e}",
        ) from e
    sub = payload.get("sub")
    if sub != SUBJECT:
        raise HTTPException(status_code=401, detail="bad subject")
    return sub
