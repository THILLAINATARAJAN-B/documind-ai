from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.redis_client import get_redis
from app.core.config import get_settings
from app.models.models import User
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    RefreshRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token()

    # Store refresh token in Redis with expiry
    redis = get_redis()
    if redis is not None:
        key = f"refresh:{user.id}:{refresh_token}"
        redis.setex(key, settings.refresh_token_expire_days * 86400, "valid")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token_endpoint(payload: RefreshRequest, db: Session = Depends(get_db)):
    """
    Exchange a valid refresh token for a new access token + rotated refresh token.
    Refresh tokens are single-use (rotated on every call).
    """
    redis = get_redis()

    if redis is None:
        raise HTTPException(503, "Token refresh unavailable (Redis not connected)")

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(401, "User not found")

    key = f"refresh:{payload.user_id}:{payload.refresh_token}"
    stored = redis.get(key)
    if not stored:
        raise HTTPException(401, "Invalid or expired refresh token")

    # Rotate: delete old token, issue new ones
    redis.delete(key)

    new_access = create_access_token({"sub": str(user.id)})
    new_refresh = create_refresh_token()
    new_key = f"refresh:{user.id}:{new_refresh}"
    redis.setex(new_key, settings.refresh_token_expire_days * 86400, "valid")

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
    )


@router.post("/logout")
def logout(payload: RefreshRequest):
    """Invalidate the refresh token (revoke session)."""
    redis = get_redis()
    if redis is not None:
        key = f"refresh:{payload.user_id}:{payload.refresh_token}"
        redis.delete(key)
    return {"detail": "Logged out"}
