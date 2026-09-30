from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User
from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.sales.models import Sale, SaleDuplicateReview, SaleItem


def user(db: Session, email: str, role: str) -> User:
    record = User(email=email, full_name=email, password_hash=hash_password("correct-password"), role=role, is_active=True)
    db.add(record)
    db.commit()
    return record


def headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "correct-password"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def customer_and_product(client: TestClient, db: Session) -> tuple[User, dict, dict, dict[str, str]]:
    advisor = user(db, "advisor@example.com", "ASESOR")
    supervisor = user(db, "supervisor@example.com", "SUPERVISOR")
    advisor_auth = headers(client, advisor.email)
    supervisor_auth = headers(client, supervisor.email)
    customer = client.post("/api/v1/customers", headers=advisor_auth, json={"dni": "70000001", "first_names": "Ana", "last_names": "Torres", "phone": "999999999"}).json()
    brand = client.post("/api/v1/brands", headers=supervisor_auth, json={"name": "Bohr"}).json()
    category = client.post("/api/v1/product-categories", headers=supervisor_auth, json={"name": "Suplementos"}).json()
    product = client.post("/api/v1/products", headers=supervisor_auth, json={"code": "COL-01", "name": "Colageno", "brand_id": brand["id"], "category_id": category["id"]}).json()
    rule = client.post(
        f"/api/v1/products/{product['id']}/rules", headers=supervisor_auth,
        json={"duration_days": 30, "alert_days": [15, 5], "effective_from": "2025-01-01"},
    )
    assert rule.status_code == 201
    return advisor, customer, product, supervisor_auth


def test_sale_snapshots_rule_and_builds_repurchase_history(client: TestClient, db: Session) -> None:
    advisor, customer, product, _ = customer_and_product(client, db)
    auth = headers(client, advisor.email)
    first = client.post("/api/v1/sales", headers=auth, json={"customer_id": customer["id"], "sale_date": "2026-01-10", "acquisition_channel": "OTROS", "acquisition_channel_detail": "Feria", "items": [{"product_id": product["id"], "quantity": 3}]})
    assert first.status_code == 201
    assert first.json()["status"] == "CONFIRMADA"
    first_item = first.json()["items"][0]
    assert first_item["purchase_type"] == "COMPRA"
    assert first_item["expected_repurchase_date"] == "2026-02-09"
    assert first_item["quantity"] == 3

    second = client.post("/api/v1/sales", headers=auth, json={"customer_id": customer["id"], "sale_date": "2026-02-10", "items": [{"product_id": product["id"], "quantity": 1}]})
    assert second.status_code == 201
    second_item = second.json()["items"][0]
    assert second_item["purchase_type"] == "RECOMPRA"
    assert second_item["prior_confirmed_item_id"] == first_item["id"]
    history = client.get(f"/api/v1/customers/{customer['id']}/sales", headers=auth)
    assert history.status_code == 200
    assert len(history.json()) == 2


def test_duplicate_needs_review_and_annulment_recomputes_chain(client: TestClient, db: Session) -> None:
    advisor, customer, product, supervisor_auth = customer_and_product(client, db)
    auth = headers(client, advisor.email)
    first = client.post("/api/v1/sales", headers=auth, json={"customer_id": customer["id"], "sale_date": "2026-01-10", "acquisition_channel": "TV", "items": [{"product_id": product["id"], "quantity": 1}]}).json()
    duplicate = client.post("/api/v1/sales", headers=auth, json={"customer_id": customer["id"], "sale_date": "2026-01-10", "items": [{"product_id": product["id"], "quantity": 1}]})
    assert duplicate.status_code == 201
    assert duplicate.json()["status"] == "PENDIENTE_REVISION_DUPLICADO"
    approved = client.post(f"/api/v1/sales/{duplicate.json()['id']}/duplicate-review", headers=supervisor_auth, json={"decision": "APROBADA", "reason": "Dos comprobantes distintos"})
    assert approved.status_code == 200
    assert approved.json()["items"][0]["purchase_type"] == "RECOMPRA"
    annulled = client.post(f"/api/v1/sales/{first['id']}/annul", headers=supervisor_auth, json={"reason": "Comprobante invalidado"})
    assert annulled.status_code == 200
    remaining = db.get(SaleItem, approved.json()["items"][0]["id"])
    assert remaining.purchase_type == "COMPRA"
    assert remaining.prior_confirmed_item_id is None
    assert db.query(SaleDuplicateReview).count() == 1
    assert db.query(AuditLog).filter_by(entity_type="sale", action="ANNULLED").count() == 1


def test_advisor_cannot_register_sale_for_another_portfolio(client: TestClient, db: Session) -> None:
    advisor, customer, product, _ = customer_and_product(client, db)
    other = user(db, "other@example.com", "ASESOR")
    denied = client.post("/api/v1/sales", headers=headers(client, other.email), json={"customer_id": customer["id"], "sale_date": str(date.today()), "acquisition_channel": "DIGITAL", "items": [{"product_id": product["id"], "quantity": 1}]})
    assert denied.status_code == 403


def test_advisor_sees_sales_for_own_portfolio(client: TestClient, db: Session) -> None:
    advisor, customer, product, supervisor_auth = customer_and_product(client, db)
    sale = client.post("/api/v1/sales", headers=supervisor_auth, json={
        "customer_id": customer["id"], "sale_date": "2026-01-10", "acquisition_channel": "TV",
        "items": [{"product_id": product["id"], "quantity": 1}],
    })
    assert sale.status_code == 201
    portfolio_sales = client.get("/api/v1/sales", headers=headers(client, advisor.email)).json()
    assert [row["id"] for row in portfolio_sales] == [sale.json()["id"]]
    assert portfolio_sales[0]["advisor_full_name"] != advisor.full_name
    assert client.get(f"/api/v1/sales/{sale.json()['id']}", headers=headers(client, advisor.email)).status_code == 200


def test_advisor_personal_metrics_only_include_confirmed_sales(client: TestClient, db: Session) -> None:
    advisor, customer, product, _ = customer_and_product(client, db)
    auth_headers = headers(client, advisor.email)
    client.post("/api/v1/sales", headers=auth_headers, json={"customer_id": customer["id"], "sale_date": "2026-01-10", "acquisition_channel": "TV", "items": [{"product_id": product["id"], "quantity": 3}]})
    client.post("/api/v1/sales", headers=auth_headers, json={"customer_id": customer["id"], "sale_date": "2026-02-10", "items": [{"product_id": product["id"], "quantity": 2}]})
    metrics = client.get("/api/v1/sales/me/metrics?date_from=2026-02-01", headers=auth_headers)
    assert metrics.status_code == 200
    assert metrics.json() == {"confirmed_sales": 1, "regular_sales": 0, "confirmed_items": 2, "repurchase_sales": 1, "repurchase_items": 2, "total_revenue": "2.00", "regular_revenue": "0.00", "repurchase_revenue": "2.00"}
    supervisor = user(db, "metrics-supervisor@example.com", "SUPERVISOR")
    assert client.get("/api/v1/sales/me/metrics", headers=headers(client, supervisor.email)).status_code == 403


def test_reports_treat_legacy_missing_sale_item_price_as_zero(client: TestClient, db: Session) -> None:
    advisor, customer, product, supervisor_auth = customer_and_product(client, db)
    sale = client.post(
        "/api/v1/sales", headers=headers(client, advisor.email),
        json={"customer_id": customer["id"], "sale_date": "2026-01-10", "acquisition_channel": "TV", "items": [{"product_id": product["id"], "quantity": 2}]},
    ).json()
    db.get(SaleItem, sale["items"][0]["id"]).unit_price = None
    db.commit()
    metrics = client.get("/api/v1/reports/metrics", headers=supervisor_auth)
    assert metrics.status_code == 200
    assert metrics.json()["total_revenue"] == "0"
    assert client.get("/api/v1/reports/operation.xlsx", headers=supervisor_auth).status_code == 200


def test_supervisor_can_register_one_replacement_for_annulled_sale(client: TestClient, db: Session) -> None:
    advisor, customer, product, supervisor_auth = customer_and_product(client, db)
    original = client.post(
        "/api/v1/sales", headers=headers(client, advisor.email),
        json={"customer_id": customer["id"], "sale_date": "2026-01-10", "acquisition_channel": "TV", "items": [{"product_id": product["id"], "quantity": 1}]},
    ).json()
    assert client.post(f"/api/v1/sales/{original['id']}/annul", headers=supervisor_auth, json={"reason": "Comprobante invalidado"}).status_code == 200
    replacement_payload = {"customer_id": customer["id"], "sale_date": "2026-01-11", "replaces_sale_id": original["id"], "items": [{"product_id": product["id"], "quantity": 2}]}
    replacement = client.post("/api/v1/sales", headers=supervisor_auth, json=replacement_payload)
    assert replacement.status_code == 201
    assert replacement.json()["replaces_sale_id"] == original["id"]
    assert replacement.json()["items"][0]["purchase_type"] == "COMPRA"
    assert client.post("/api/v1/sales", headers=supervisor_auth, json=replacement_payload).status_code == 409


def test_supervisor_edits_and_hard_deletes_sale_with_alert_dependents(client: TestClient, db: Session) -> None:
    advisor, customer, product, supervisor_auth = customer_and_product(client, db)
    advisor_auth = headers(client, advisor.email)
    sale = client.post("/api/v1/sales", headers=advisor_auth, json={
        "customer_id": customer["id"], "sale_date": "2026-01-10", "acquisition_channel": "TV",
        "notes": "Initial note", "items": [{"product_id": product["id"], "quantity": 1}],
    }).json()
    listed = client.get("/api/v1/sales", headers=supervisor_auth).json()[0]
    assert listed["customer_first_names"] == "Ana"
    assert listed["advisor_full_name"] == advisor.full_name
    assert listed["items"][0]["product_name"] == "Colageno"
    assert client.patch(f"/api/v1/sales/{sale['id']}", headers=advisor_auth, json={"notes": "Denied"}).status_code == 403
    edited = client.patch(f"/api/v1/sales/{sale['id']}", headers=supervisor_auth, json={
        "sale_date": "2026-01-12", "notes": "Corrected", "items": [{"product_id": product["id"], "quantity": 2}],
    })
    assert edited.status_code == 200
    assert edited.json()["items"][0]["expected_repurchase_date"] == "2026-02-11"
    assert edited.json()["items"][0]["unit_price"] == "1.00"
    alert = Alert(sale_item_id=edited.json()["items"][0]["id"], alert_date=date(2026, 2, 11), expected_repurchase_date=date(2026, 2, 11))
    db.add(alert)
    db.flush()
    alert_id = alert.id
    db.add(AlertContactAttempt(alert_id=alert.id, advisor_id=advisor.id, channel="LLAMADA", result="OTRO"))
    linked_sale = Sale(customer_id=customer["id"], advisor_id=advisor.id, sale_date=date(2026, 3, 1), status="RECHAZADA_DUPLICADO", source_alert_id=alert_id)
    db.add(linked_sale)
    db.commit()
    blocked = client.patch(
        f"/api/v1/sales/{sale['id']}", headers=supervisor_auth,
        json={"sale_date": "2026-01-13", "items": [{"product_id": product["id"], "quantity": 3}]},
    )
    assert blocked.status_code == 409
    assert "annul and register a replacement" in blocked.json()["detail"]
    assert db.query(SaleItem).filter_by(sale_id=sale["id"]).count() == 1
    assert db.query(Alert).filter_by(id=alert_id).count() == 1
    assert db.query(AlertContactAttempt).filter_by(alert_id=alert_id).count() == 1
    assert db.get(Sale, linked_sale.id).source_alert_id == alert_id
    assert client.delete(f"/api/v1/sales/{sale['id']}", headers=advisor_auth).status_code == 403
    assert client.delete(f"/api/v1/sales/{sale['id']}", headers=supervisor_auth).status_code == 204
    assert db.get(Sale, sale["id"]) is None
    assert db.query(SaleItem).filter_by(sale_id=sale["id"]).count() == 0
    assert db.query(Alert).filter_by(id=alert_id).count() == 0
    assert db.query(AlertContactAttempt).filter_by(alert_id=alert_id).count() == 0
    db.expire_all()
    assert db.get(Sale, linked_sale.id).source_alert_id is None
    audit = db.query(AuditLog).filter_by(entity_type="sale", entity_id=sale["id"], action="HARD_DELETED").one()
    assert audit.before_data["notes"] == "Corrected"
