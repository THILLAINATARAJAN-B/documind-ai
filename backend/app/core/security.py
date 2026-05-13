import bcrypt
import secrets
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from app.core.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token() -> str:
    """Generate a secure random refresh token (opaque, stored in Redis)."""
    return secrets.token_urlsafe(48)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        # Reject refresh tokens used as access tokens
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


# Alias used by routers/auth.py for backward-compatibility
decode_token = decode_access_token
