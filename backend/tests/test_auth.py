from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.auth.models import User


def create_user(db: Session, *, role: str = "ASESOR", is_active: bool = True) -> User:
    user = User(
        email="asesor@example.com",
        full_name="Asesor de prueba",
        password_hash=hash_password("correct-password"),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    return user


def test_login_and_me(client: TestClient, db: Session) -> None:
    create_user(db)

    login = client.post("/api/v1/auth/login", json={"email": "asesor@example.com", "password": "correct-password"})

    assert login.status_code == 200
    token = login.json()["access_token"]
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["role"] == "ASESOR"


def test_login_rejects_invalid_credentials(client: TestClient, db: Session) -> None:
    create_user(db)

    response = client.post("/api/v1/auth/login", json={"email": "asesor@example.com", "password": "wrong-password"})

    assert response.status_code == 401


def test_inactive_user_cannot_login(client: TestClient, db: Session) -> None:
    create_user(db, is_active=False)

    response = client.post("/api/v1/auth/login", json={"email": "asesor@example.com", "password": "correct-password"})

    assert response.status_code == 401


def test_admin_route_requires_admin_role(client: TestClient, db: Session) -> None:
    create_user(db)
    token = client.post(
        "/api/v1/auth/login", json={"email": "asesor@example.com", "password": "correct-password"}
    ).json()["access_token"]

    response = client.get("/api/v1/users/admin-check", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
