from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hash.verify(password, stored_hash)


def create_access_token(user_id: str, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": user_id, "role": role, "exp": expires_at}, settings.app_secret_key, algorithm="HS256")


def create_reset_token() -> str:
    return uuid4().hex + uuid4().hex


def decode_access_token(token: str) -> dict[str, str]:
    return jwt.decode(token, settings.app_secret_key, algorithms=["HS256"])
