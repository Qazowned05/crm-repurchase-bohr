from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User


def user(db: Session, email: str, role: str) -> User:
    record = User(
        email=email,
        full_name=email.split("@")[0],
        password_hash=hash_password("correct-password"),
        role=role,
        is_active=True,
    )
    db.add(record)
    db.commit()
    return record


def headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "correct-password"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_advisor_owns_created_customer(client: TestClient, db: Session) -> None:
    advisor = user(db, "advisor@example.com", "ASESOR")
    another_advisor = user(db, "other@example.com", "ASESOR")
    created = client.post(
        "/api/v1/customers",
        headers=headers(client, advisor.email),
        json={"dni": "70000001", "first_names": "Ana", "last_names": "Torres", "phone": "999999999"},
    )

    assert created.status_code == 201
    assert created.json()["responsible_advisor_id"] == advisor.id
    forbidden = client.get(f"/api/v1/customers/{created.json()['id']}", headers=headers(client, another_advisor.email))
    assert forbidden.status_code == 403
    assert db.query(AuditLog).filter_by(entity_type="customer", action="CREATED").count() == 1


def test_supervisor_creates_product_and_versioned_rule(client: TestClient, db: Session) -> None:
    supervisor = user(db, "supervisor@example.com", "SUPERVISOR")
    auth = headers(client, supervisor.email)
    product = client.post("/api/v1/products", headers=auth, json={"code": "COL-001", "name": "Colageno", "category": "Suplementos"})

    assert product.status_code == 201
    invalid_rule = client.post(
        f"/api/v1/products/{product.json()['id']}/rules",
        headers=auth,
        json={
            "duration_days": 30, "alert_days": [30], "effective_from": "2026-10-01",
            "medical_approval_reference": "MED-01", "medical_approved_by": "Dra. Vega",
            "medical_approved_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert invalid_rule.status_code == 422
    valid_rule = client.post(
        f"/api/v1/products/{product.json()['id']}/rules",
        headers=auth,
        json={
            "duration_days": 30, "alert_days": [15, 5], "effective_from": "2026-10-01",
            "medical_approval_reference": "MED-01", "medical_approved_by": "Dra. Vega",
            "medical_approved_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert valid_rule.status_code == 201
    assert valid_rule.json()["alert_days"] == [15, 5]


def test_only_admin_manages_users(client: TestClient, db: Session) -> None:
    supervisor = user(db, "supervisor@example.com", "SUPERVISOR")
    admin = user(db, "admin@example.com", "ADMIN")

    denied = client.post(
        "/api/v1/users",
        headers=headers(client, supervisor.email),
        json={"email": "new@example.com", "full_name": "New User", "password": "correct-password", "role": "ASESOR"},
    )
    assert denied.status_code == 403
    created = client.post(
        "/api/v1/users",
        headers=headers(client, admin.email),
        json={"email": "new@example.com", "full_name": "New User", "password": "correct-password", "role": "ASESOR"},
    )
    assert created.status_code == 201
    assert created.json()["role"] == "ASESOR"
