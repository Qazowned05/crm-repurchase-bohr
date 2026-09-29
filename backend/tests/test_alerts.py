from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User
from app.modules.sales.models import Sale


def make_user(db: Session, email: str, role: str, active: bool = True) -> User:
    record = User(email=email, full_name=email, password_hash=hash_password("correct-password"), role=role, is_active=active)
    db.add(record)
    db.commit()
    return record


def auth(client: TestClient, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': email, 'password': 'correct-password'}).json()['access_token']}"}


def setup_sale(client: TestClient, db: Session, sale_date: date, duration: int = 30, suffix: str = "") -> tuple[dict, dict, dict[str, str], User]:
    advisor = make_user(db, f"advisor-alert{suffix}@example.com", "ASESOR")
    supervisor = make_user(db, f"supervisor-alert{suffix}@example.com", "SUPERVISOR")
    advisor_auth, supervisor_auth = auth(client, advisor.email), auth(client, supervisor.email)
    customer = client.post("/api/v1/customers", headers=advisor_auth, json={"dni": f"8000000{suffix or '1'}", "first_names": "Alicia", "last_names": "Rios", "phone": "999999999"}).json()
    brand = client.post("/api/v1/brands", headers=supervisor_auth, json={"name": f"Marca {suffix or '1'}"}).json()
    category = client.post("/api/v1/product-categories", headers=supervisor_auth, json={"name": f"Categoria {suffix or '1'}"}).json()
    product = client.post("/api/v1/products", headers=supervisor_auth, json={"code": f"ALT-0{suffix or '1'}", "name": "Producto alerta", "brand_id": brand["id"], "category_id": category["id"]}).json()
    assert client.post(f"/api/v1/products/{product['id']}/rules", headers=supervisor_auth, json={"duration_days": duration, "alert_days": [15, 5], "effective_from": "2020-01-01"}).status_code == 201
    sale = client.post("/api/v1/sales", headers=advisor_auth, json={"customer_id": customer["id"], "sale_date": str(sale_date), "acquisition_channel": "TV", "items": [{"product_id": product["id"], "quantity": 1}]}).json()
    return sale, product, supervisor_auth, advisor


def add_product_with_rule(client: TestClient, supervisor_auth: dict[str, str], original: dict, suffix: str, duration: int, unit_price: str = "1.00") -> dict:
    product = client.post("/api/v1/products", headers=supervisor_auth, json={
        "code": f"EXTRA-{suffix}", "name": f"Producto extra {suffix}",
        "brand_id": original["brand_id"], "category_id": original["category_id"], "unit_price": unit_price,
    }).json()
    assert client.post(f"/api/v1/products/{product['id']}/rules", headers=supervisor_auth, json={
        "duration_days": duration, "alert_days": [10, 3], "effective_from": "2020-01-01",
    }).status_code == 201
    return product


def test_automatic_generation_is_idempotent_and_uses_due_date(client: TestClient, db: Session) -> None:
    run_date = date.today()
    sale, _, supervisor_auth, advisor = setup_sale(client, db, run_date - timedelta(days=30))
    assert client.get("/api/v1/alerts/inbox", headers=supervisor_auth).status_code == 200
    assert client.get("/api/v1/alerts/inbox", headers=supervisor_auth).status_code == 200
    alert = db.query(Alert).one()
    assert alert.sale_item_id == sale["items"][0]["id"]
    assert alert.assigned_advisor_id == advisor.id
    assert alert.alert_date == alert.expected_repurchase_date == run_date
    assert client.post("/api/v1/alerts/generate", headers=supervisor_auth).status_code == 405


def test_inbox_generates_today_alert_without_manual_generation(client: TestClient, db: Session) -> None:
    sale, _, _, advisor = setup_sale(client, db, date.today() - timedelta(days=30), suffix="inbox")
    response = client.get("/api/v1/alerts/inbox", headers=auth(client, advisor.email))
    assert response.status_code == 200
    assert [alert["sale_item_id"] for alert in response.json()] == [sale["items"][0]["id"]]
    assert db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).count() == 1
    audit = db.query(AuditLog).filter_by(entity_type="alert", action="GENERATED").one()
    assert audit.actor_id is None and audit.after_data["generation_actor"] == "SYSTEM"


def test_past_sale_creates_one_pending_or_expired_alert(client: TestClient, db: Session) -> None:
    recent, _, supervisor_auth, _ = setup_sale(client, db, date.today() - timedelta(days=40), duration=30)
    assert client.get("/api/v1/alerts/inbox", headers=supervisor_auth).status_code == 200
    old, _, _, _ = setup_sale(client, db, date.today() - timedelta(days=70), duration=30, suffix="2")
    assert client.get("/api/v1/alerts/inbox", headers=supervisor_auth).status_code == 200
    assert db.query(Alert).filter_by(sale_item_id=recent["items"][0]["id"]).count() == 1
    assert db.query(Alert).filter_by(sale_item_id=old["items"][0]["id"], status="VENCIDO_NO_GESTIONADO").count() == 1
    assert db.query(Alert).filter_by(sale_item_id=recent["items"][0]["id"]).one().alert_date == date.today() - timedelta(days=10)
    assert db.query(Alert).filter_by(sale_item_id=old["items"][0]["id"]).one().alert_date == date.today() - timedelta(days=40)


def test_contact_attempt_validates_and_reprograms_inbox(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30))
    client.get("/api/v1/alerts/inbox", headers=supervisor_auth)
    alert = db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).one()
    advisor_auth = auth(client, advisor.email)
    invalid = client.post(f"/api/v1/alerts/{alert.id}/attempts", headers=advisor_auth, json={"channel": "LLAMADA", "result": "SIN_RESPUESTA"})
    assert invalid.status_code == 422
    result = client.post(f"/api/v1/alerts/{alert.id}/attempts", headers=advisor_auth, json={"channel": "WHATSAPP", "result": "AUN_TIENE_PRODUCTO", "next_action_date": str(date.today() + timedelta(days=3))})
    assert result.status_code == 200 and result.json()["status"] == "REPROGRAMADO"
    assert db.query(AlertContactAttempt).filter_by(alert_id=alert.id).count() == 1
    assert client.get("/api/v1/alerts/inbox", headers=advisor_auth).json() == []
    alert.next_action_date = date.today()
    db.commit()
    assert client.get("/api/v1/alerts/inbox", headers=advisor_auth).json()[0]["id"] == alert.id


def test_reassigned_alert_reprograms_for_a_typification_with_next_action(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30), suffix="reagenda")
    typification = client.post(
        "/api/v1/configuration/contact-typifications", headers=supervisor_auth,
        json={"code": "CLIENTE_REAGENDA", "name": "Cliente reagenda", "requires_next_action": True},
    ).json()
    alert = client.get("/api/v1/alerts/inbox", headers=supervisor_auth).json()[0]
    db.get(Alert, alert["id"]).status = "REASIGNADO"
    db.commit()

    response = client.post(
        f"/api/v1/alerts/{alert['id']}/attempts", headers=auth(client, advisor.email),
        json={"channel": "LLAMADA", "typification_id": typification["id"], "result": typification["code"], "next_action_date": str(date.today() + timedelta(days=1))},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REPROGRAMADO"
    assert response.json()["customer_id"] == sale["customer_id"]


def test_confirmed_repurchase_and_annulment_close_active_alerts(client: TestClient, db: Session) -> None:
    sale, product, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30))
    client.get("/api/v1/alerts/inbox", headers=supervisor_auth)
    first_alert = db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).one()
    advisor_auth = auth(client, advisor.email)
    repurchase = client.post("/api/v1/sales", headers=advisor_auth, json={"customer_id": sale["customer_id"], "sale_date": str(date.today()), "source_alert_id": first_alert.id, "items": [{"product_id": product["id"], "quantity": 1}]}).json()
    db.refresh(first_alert)
    assert first_alert.status == "RECOMPRA_LOGRADA"
    assert first_alert.closure_reason == f"RECOMPRA_CONFIRMADA: venta {repurchase['id']}"
    assert repurchase["items"][0]["expected_repurchase_date"] == str(date.today() + timedelta(days=30))
    new_alert = Alert(sale_item_id=repurchase["items"][0]["id"], assigned_advisor_id=advisor.id, alert_date=date.today(), expected_repurchase_date=date.today() + timedelta(days=30))
    db.add(new_alert)
    db.commit()
    assert client.post(f"/api/v1/sales/{repurchase['id']}/annul", headers=supervisor_auth, json={"reason": "Venta anulada"}).status_code == 200
    db.refresh(new_alert)
    assert new_alert.status == "CANCELADO_POR_ANULACION"


def test_managed_register_keeps_follow_up_and_closed_alert_history(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30), suffix="register")
    parent = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={"code": "CONTACTED_REGISTER", "name": "Contacted"}).json()
    child = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={
        "code": "CONTACTED_REGISTER_DONE", "name": "Completed", "parent_id": parent["id"], "requires_close": True,
    }).json()
    alert = client.get("/api/v1/alerts/inbox", headers=supervisor_auth).json()[0]
    advisor_auth = auth(client, advisor.email)
    assert client.post(f"/api/v1/alerts/{alert['id']}/attempts", headers=advisor_auth, json={
        "channel": "LLAMADA", "result": "ignored", "typification_id": child["id"], "note": "Customer confirmed closure",
    }).status_code == 200

    closed = client.get(f"/api/v1/alerts/register?state=closed&date_from={date.today()}&date_to={date.today()}", headers=advisor_auth)
    assert closed.status_code == 200
    record = closed.json()[0]
    assert record["id"] == alert["id"]
    assert record["status"] == "CERRADO_POR_TIPIFICACION"
    assert record["closure_reason"] == "TIPIFICACION_DE_CIERRE: Completed"
    assert record["customer_id"] == sale["customer_id"]
    assert record["contact_attempts"] == [{
        "id": record["contact_attempts"][0]["id"], "alert_id": alert["id"], "advisor_id": advisor.id,
        "contacted_at": record["contact_attempts"][0]["contacted_at"], "channel": "LLAMADA", "result": "CONTACTED_REGISTER_DONE",
        "note": "Customer confirmed closure", "next_action_date": None, "observation": "Customer confirmed closure",
        "user_name": advisor.full_name, "parent_typification_name": "Contacted", "child_typification_name": "Completed",
    }]
    assert client.get("/api/v1/alerts/register?state=open-follow-up", headers=advisor_auth).json() == []
    assert len(client.get("/api/v1/alerts/register?state=closed", headers=supervisor_auth).json()) == 1
    assert client.get("/api/v1/alerts/register?date_from=2030-01-02&date_to=2030-01-01", headers=supervisor_auth).status_code == 422


def test_managed_purchase_of_different_product_keeps_source_alert_recoverable(client: TestClient, db: Session) -> None:
    sale, original, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30), suffix="different")
    extra = add_product_with_rule(client, supervisor_auth, original, "different", 45, unit_price="19.90")
    alert = client.get("/api/v1/alerts/inbox", headers=supervisor_auth).json()[0]

    response = client.post(f"/api/v1/alerts/{alert['id']}/repurchase", headers=auth(client, advisor.email), json={
        "items": [{"product_id": extra["id"], "quantity": 2}],
    })

    assert response.status_code == 201
    registered = response.json()
    assert registered["source_alert_id"] == alert["id"]
    assert registered["advisor_id"] == advisor.id
    item = registered["items"][0]
    assert item["product_id"] == extra["id"]
    assert item["quantity"] == 2
    assert item["unit_price"] == "19.90"
    assert item["purchase_type"] == "COMPRA"
    assert item["expected_repurchase_date"] == str(date.today() + timedelta(days=45))
    source = db.get(Alert, alert["id"])
    assert source.status == "COMPRA_OTRO_PRODUCTO"
    assert source.closure_reason == f"COMPRA_OTRO_PRODUCTO: venta {registered['id']}"
    recovery = client.get("/api/v1/supervision/recovery-alerts", headers=supervisor_auth)
    assert [row["id"] for row in recovery.json()] == [alert["id"]]
    reassigned = client.post(
        f"/api/v1/supervision/alerts/{alert['id']}/assign", headers=supervisor_auth,
        json={"assigned_advisor_id": advisor.id, "reason": "Recuperar producto original"},
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["status"] == "REASIGNADO"
    assert sale["items"][0]["product_id"] != registered["items"][0]["product_id"]


def test_managed_repurchase_marks_only_included_original_product_as_repurchase(client: TestClient, db: Session) -> None:
    _, original, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30), suffix="mixed")
    extra = add_product_with_rule(client, supervisor_auth, original, "mixed", 20)
    alert = client.get("/api/v1/alerts/inbox", headers=supervisor_auth).json()[0]

    response = client.post(f"/api/v1/alerts/{alert['id']}/repurchase", headers=auth(client, advisor.email), json={
        "sale_date": str(date.today()),
        "notes": "Cliente recompra y agrega producto",
        "items": [
            {"product_id": original["id"], "quantity": 1, "unit_price": "30.00"},
            {"product_id": extra["id"], "quantity": 3, "unit_price": "12.50"},
        ],
    })

    assert response.status_code == 201
    items = {item["product_id"]: item for item in response.json()["items"]}
    assert items[original["id"]]["purchase_type"] == "RECOMPRA"
    assert items[extra["id"]]["purchase_type"] == "COMPRA"
    assert items[original["id"]]["expected_repurchase_date"] == str(date.today() + timedelta(days=30))
    assert items[extra["id"]]["expected_repurchase_date"] == str(date.today() + timedelta(days=20))


def test_managed_repurchase_requires_assignment_and_is_idempotent(client: TestClient, db: Session) -> None:
    _, original, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30), suffix="retry")
    alert = client.get("/api/v1/alerts/inbox", headers=supervisor_auth).json()[0]
    other = make_user(db, "other-alert@example.com", "ASESOR")
    payload = {"items": [{"product_id": original["id"], "quantity": 1, "unit_price": "22.00"}]}

    assert client.post(f"/api/v1/alerts/{alert['id']}/repurchase", headers=auth(client, other.email), json=payload).status_code == 403
    first = client.post(f"/api/v1/alerts/{alert['id']}/repurchase", headers=supervisor_auth, json=payload)
    retry = client.post(f"/api/v1/alerts/{alert['id']}/repurchase", headers=auth(client, advisor.email), json=payload)

    assert first.status_code == 201
    assert first.json()["advisor_id"] == advisor.id
    assert retry.status_code == 200
    assert retry.json()["id"] == first.json()["id"]
    assert db.query(Alert).filter_by(id=alert["id"], status="RECOMPRA_LOGRADA").count() == 1
    assert db.query(Sale).filter_by(source_alert_id=alert["id"]).count() == 1
