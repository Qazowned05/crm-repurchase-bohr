from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, create_reset_token, hash_password, verify_password
from app.dependencies import get_current_user
from app.modules.auth.models import PasswordResetToken, User
from app.modules.auth.schemas import (
    LoginRequest,
    PasswordResetAccepted,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/password-reset", response_model=PasswordResetAccepted, status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> PasswordResetAccepted:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.is_active:
        return PasswordResetAccepted()

    raw_token = create_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.reset_token_minutes)
    db.add(PasswordResetToken(user_id=user.id, token_hash=hash_password(raw_token), expires_at=expires_at))
    db.commit()
    # Delivery is deliberately externalized; development exposes expiration only, never the token.
    return PasswordResetAccepted(expires_at=expires_at if settings.app_env == "development" else None)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)) -> None:
    records = db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.used_at.is_(None), PasswordResetToken.expires_at > datetime.now(timezone.utc)
        )
    ).all()
    record = next((item for item in records if verify_password(payload.token, item.token_hash)), None)
    if record is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown user")
    user.password_hash = hash_password(payload.password)
    record.used_at = datetime.now(timezone.utc)
    db.commit()
