from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.security import hash_password
from app.dependencies import require_roles
from app.modules.auth.models import User
from app.modules.auth.schemas import UserResponse

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/admin-check", response_model=UserResponse)
def admin_check(current_user: User = Depends(require_roles("ADMIN"))) -> User:
    return current_user


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["ASESOR", "SUPERVISOR", "ADMIN"]


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: Literal["ASESOR", "SUPERVISOR", "ADMIN"] | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


@router.get("", response_model=list[UserResponse])
def list_users(
    _: User = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.full_name)))


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate, current_user: User = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)
) -> User:
    if db.scalar(select(User).where(User.email == payload.email.lower())) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        actor_id=current_user.id,
        entity_type="user",
        entity_id=user.id,
        action="CREATED",
        after={"email": user.email, "role": user.role, "is_active": user.is_active},
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    current_user: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if user.id == current_user.id and changes.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account")
    before = {"full_name": user.full_name, "role": user.role, "is_active": user.is_active}
    if "password" in changes:
        user.password_hash = hash_password(changes.pop("password"))
    for field, value in changes.items():
        setattr(user, field, value)
    record_audit(
        db,
        actor_id=current_user.id,
        entity_type="user",
        entity_id=user.id,
        action="UPDATED",
        before=before,
        after={"full_name": user.full_name, "role": user.role, "is_active": user.is_active},
    )
    db.commit()
    db.refresh(user)
    return user
