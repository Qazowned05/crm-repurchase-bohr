from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.auth.models import User


def main() -> None:
    if not settings.initial_admin_email or not settings.initial_admin_password:
        return
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == settings.initial_admin_email.lower()))
        if existing is not None:
            return
        db.add(
            User(
                email=settings.initial_admin_email.lower(),
                full_name="Administrador inicial",
                password_hash=hash_password(settings.initial_admin_password),
                role="ADMIN",
                is_active=True,
            )
        )
        db.commit()


if __name__ == "__main__":
    main()
