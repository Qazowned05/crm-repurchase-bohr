from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.imports.models import ImportJob, ImportRowError
from app.modules.products.models import Product, ProductRepurchaseRule


def make_user(db: Session, email: str, role: str) -> User:
    record = User(email=email, full_name=email, password_hash=hash_password("correct-password"), role=role, is_active=True)
    db.add(record)
    db.commit()
    return record


def auth(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "correct-password"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def workbook(headers: list[str], rows: list[list[object]], formula: bool = False) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = "Data"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    if formula:
        sheet["B2"] = "=1+1"
    output = BytesIO(); book.save(output)
    return output.getvalue()


CUSTOMER_HEADERS = ["dni", "first_names", "last_names", "phone", "email", "responsible_advisor_email"]
PRODUCT_HEADERS = ["code", "name", "brand", "category", "is_active", "duration_days", "alert_days", "effective_from"]


def preview(client: TestClient, headers: dict[str, str], import_type: str, content: bytes, **data: str) -> dict:
    response = client.post(f"/api/v1/imports/{import_type}/preview", headers=headers, data=data, files={"file": ("upload.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert response.status_code == 201, response.text
    return response.json()


def test_import_templates_and_import_access_are_supervisor_only(client: TestClient, db: Session) -> None:
    advisor = make_user(db, "advisor-import@example.com", "ASESOR")
    denied = client.get("/api/v1/imports/templates/customers", headers=auth(client, advisor.email))
    assert denied.status_code == 403
    supervisor = make_user(db, "supervisor-import@example.com", "SUPERVISOR")
    template = client.get("/api/v1/imports/templates/customers", headers=auth(client, supervisor.email))
    assert template.status_code == 200
    assert template.content.startswith(b"PK")


def test_preview_persists_formula_and_duplicate_errors(client: TestClient, db: Session) -> None:
    supervisor = make_user(db, "preview@example.com", "SUPERVISOR")
    result = preview(client, auth(client, supervisor.email), "customers", workbook(CUSTOMER_HEADERS, [["70000001", "Ana", "Torres", "999999999", "ana@example.com", ""], ["70000001", "Beto", "Diaz", "999999998", "beto@example.com", ""]], formula=True))
    assert result["state"] == "PREVIEW_ERRORS"
    assert result["rejected_rows"] >= 1
    assert db.query(ImportJob).count() == 1
    assert db.query(ImportRowError).count() >= 1
    assert client.post(f"/api/v1/imports/{result['id']}/commit", headers=auth(client, supervisor.email)).status_code == 409


def test_clean_import_commits_customers_and_versioned_product_rule(client: TestClient, db: Session) -> None:
    supervisor = make_user(db, "commit@example.com", "SUPERVISOR")
    headers = auth(client, supervisor.email)
    customer_job = preview(client, headers, "customers", workbook(CUSTOMER_HEADERS, [["70000001", "Ana", "Torres", "999999999", "ana@example.com", ""]]))
    committed = client.post(f"/api/v1/imports/{customer_job['id']}/commit", headers=headers)
    assert committed.status_code == 200
    assert committed.json()["state"] == "COMMITTED"
    assert db.query(Customer).count() == 1
    assert client.post("/api/v1/brands", headers=headers, json={"name": "Bohr"}).status_code == 201
    assert client.post("/api/v1/product-categories", headers=headers, json={"name": "Suplementos"}).status_code == 201
    product_job = preview(client, headers, "products", workbook(PRODUCT_HEADERS, [["COL-001", "Colageno", "Bohr", "Suplementos", "true", "30", "15,5", "2026-01-01"]]))
    assert client.post(f"/api/v1/imports/{product_job['id']}/commit", headers=headers).status_code == 200
    assert db.query(Product).count() == 1
    assert db.query(ProductRepurchaseRule).count() == 1


def test_product_import_rejects_unknown_catalog_values(client: TestClient, db: Session) -> None:
    supervisor = make_user(db, "catalog-import@example.com", "SUPERVISOR")
    result = preview(client, auth(client, supervisor.email), "products", workbook(PRODUCT_HEADERS, [["COL-404", "Colageno", "Desconocida", "Suplementos", "true", "", "", ""]]))
    assert result["state"] == "PREVIEW_ERRORS"
    assert "existing active catalog" in result["errors"][0]["message"]
