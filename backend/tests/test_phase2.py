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


def catalog(client: TestClient, auth: dict[str, str]) -> tuple[dict, dict]:
    brand = client.post("/api/v1/brands", headers=auth, json={"name": "Bohr"}).json()
    category = client.post("/api/v1/product-categories", headers=auth, json={"name": "Suplementos"}).json()
    return brand, category


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


def test_customer_segmentation_is_optional_and_returned(client: TestClient, db: Session) -> None:
    advisor = user(db, "advisor@example.com", "ASESOR")
    auth = headers(client, advisor.email)
    created = client.post(
        "/api/v1/customers",
        headers=auth,
        json={
            "dni": "70000002", "first_names": "Beatriz", "last_names": "Luna", "phone": "988888888",
            "condition": "Hipertensión", "birth_date": "1984-03-10",
            "department": "LIMA", "province": "LIMA", "district": "MIRAFLORES", "ubigeo": "150122",
        },
    )

    assert created.status_code == 201
    assert created.json()["condition"] == "Hipertensión"
    assert created.json()["birth_date"] == "1984-03-10"
    assert created.json()["district"] == "MIRAFLORES"
    partial = client.patch(f"/api/v1/customers/{created.json()['id']}", headers=auth, json={"district": "SAN ISIDRO"})
    assert partial.status_code == 422
    updated = client.patch(f"/api/v1/customers/{created.json()['id']}", headers=auth, json={
        "department": "LIMA", "province": "LIMA", "district": "SAN ISIDRO", "ubigeo": "150131",
    })
    assert updated.status_code == 200
    assert updated.json()["district"] == "SAN ISIDRO"


def test_supervisor_customer_assignment_makes_customer_visible_to_advisor(client: TestClient, db: Session) -> None:
    supervisor = user(db, "supervisor-customer@example.com", "SUPERVISOR")
    advisor = user(db, "portfolio-customer@example.com", "ASESOR")
    created = client.post(
        "/api/v1/customers",
        headers=headers(client, supervisor.email),
        json={
            "dni": "70000003", "first_names": "Carmen", "last_names": "Rios", "phone": "977777777",
            "responsible_advisor_id": advisor.id,
        },
    )

    assert created.status_code == 201
    assert created.json()["responsible_advisor_id"] == advisor.id
    visible = client.get("/api/v1/customers", headers=headers(client, advisor.email))
    assert [customer["id"] for customer in visible.json()] == [created.json()["id"]]


def test_active_customer_is_available_for_sales_without_changing_portfolio(client: TestClient, db: Session) -> None:
    supervisor = user(db, "supervisor-sales-options@example.com", "SUPERVISOR")
    owner = user(db, "owner-sales-options@example.com", "ASESOR")
    seller = user(db, "seller-sales-options@example.com", "ASESOR")
    created = client.post(
        "/api/v1/customers",
        headers=headers(client, supervisor.email),
        json={
            "dni": "70000004", "first_names": "Diana", "last_names": "Vega", "phone": "966666666",
            "responsible_advisor_id": owner.id,
        },
    ).json()

    portfolio = client.get("/api/v1/customers", headers=headers(client, seller.email))
    sale_options = client.get("/api/v1/customers/sale-options", headers=headers(client, seller.email))
    assert portfolio.json() == []
    assert sale_options.json() == []
    owner_options = client.get("/api/v1/customers/sale-options", headers=headers(client, owner.email))
    assert [customer["id"] for customer in owner_options.json()] == [created["id"]]


def test_supervisor_creates_product_and_versioned_rule(client: TestClient, db: Session) -> None:
    supervisor = user(db, "supervisor@example.com", "SUPERVISOR")
    auth = headers(client, supervisor.email)
    brand, category = catalog(client, auth)
    product = client.post("/api/v1/products", headers=auth, json={"code": "COL-001", "name": "Colageno", "brand_id": brand["id"], "category_id": category["id"]})

    assert product.status_code == 201
    updated_product = client.patch(f"/api/v1/products/{product.json()['id']}", headers=auth, json={"unit_price": "19.90"})
    assert updated_product.status_code == 200
    assert updated_product.json()["unit_price"] == "19.90"
    invalid_rule = client.post(
        f"/api/v1/products/{product.json()['id']}/rules",
        headers=auth,
        json={
            "duration_days": 30, "alert_days": [30], "effective_from": "2026-10-01",
        },
    )
    assert invalid_rule.status_code == 422
    valid_rule = client.post(
        f"/api/v1/products/{product.json()['id']}/rules",
        headers=auth,
        json={
            "duration_days": 30, "alert_days": [15, 5], "effective_from": "2026-10-01",
        },
    )
    assert valid_rule.status_code == 201
    assert valid_rule.json()["alert_days"] == [15, 5]
    assert valid_rule.json().keys().isdisjoint({"medical_approval_reference", "medical_approved_by", "medical_approved_at"})


def test_catalog_crud_is_restricted_and_deletion_is_guarded(client: TestClient, db: Session) -> None:
    advisor = user(db, "catalog-advisor@example.com", "ASESOR")
    supervisor = user(db, "catalog-supervisor@example.com", "SUPERVISOR")
    denied = client.post("/api/v1/brands", headers=headers(client, advisor.email), json={"name": "Bohr"})
    assert denied.status_code == 403
    auth = headers(client, supervisor.email)
    brand, category = catalog(client, auth)
    product = client.post("/api/v1/products", headers=auth, json={"code": "CAT-001", "name": "Catalogado", "brand_id": brand["id"], "category_id": category["id"]})
    assert product.status_code == 201
    assert product.json()["brand_name"] == "Bohr"
    assert product.json()["category_name"] == "Suplementos"
    assert client.delete(f"/api/v1/brands/{brand['id']}", headers=auth).status_code == 409
    assert client.patch(f"/api/v1/brands/{brand['id']}", headers=auth, json={"is_active": False}).json()["is_active"] is False


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
