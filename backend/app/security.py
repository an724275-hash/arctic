"""Password hashing and short-lived bearer tokens."""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets

import jwt
from pwdlib import PasswordHash

from app.config import settings

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hasher.verify(password, hashed)
    except (ValueError, TypeError):
        return False


def create_access_token(user) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
            "type": "access",
            "tv": user.token_version,
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
            "jti": secrets.token_hex(16),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def new_secret() -> str:
    return secrets.token_urlsafe(48)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
