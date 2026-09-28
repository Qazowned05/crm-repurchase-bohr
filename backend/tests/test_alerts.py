from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User


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


def test_generation_is_idempotent_and_uses_current_responsible_advisor(client: TestClient, db: Session) -> None:
    run_date = date.today()
    sale, _, supervisor_auth, advisor = setup_sale(client, db, run_date - timedelta(days=15))
    first = client.post(f"/api/v1/alerts/generate?run_date={run_date}", headers=supervisor_auth)
    assert first.status_code == 200 and first.json()["created"] == 1
    assert client.post(f"/api/v1/alerts/generate?run_date={run_date}", headers=supervisor_auth).json()["created"] == 0
    alert = db.query(Alert).one()
    assert alert.sale_item_id == sale["items"][0]["id"]
    assert alert.assigned_advisor_id == advisor.id


def test_inbox_generates_today_alert_without_manual_generation(client: TestClient, db: Session) -> None:
    sale, _, _, advisor = setup_sale(client, db, date.today() - timedelta(days=15), suffix="inbox")
    response = client.get("/api/v1/alerts/inbox", headers=auth(client, advisor.email))
    assert response.status_code == 200
    assert [alert["sale_item_id"] for alert in response.json()] == [sale["items"][0]["id"]]
    assert db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).count() == 1
    audit = db.query(AuditLog).filter_by(entity_type="alert", action="GENERATED").one()
    assert audit.actor_id is None and audit.after_data["generation_actor"] == "SYSTEM"


def test_past_sale_creates_one_pending_or_expired_alert(client: TestClient, db: Session) -> None:
    recent, _, supervisor_auth, _ = setup_sale(client, db, date.today() - timedelta(days=40), duration=30)
    response = client.post("/api/v1/alerts/generate", headers=supervisor_auth)
    assert response.json()["pending"] == 1
    old, _, _, _ = setup_sale(client, db, date.today() - timedelta(days=70), duration=30, suffix="2")
    response = client.post("/api/v1/alerts/generate", headers=supervisor_auth)
    assert response.json()["expired"] == 1
    assert db.query(Alert).filter_by(sale_item_id=recent["items"][0]["id"]).count() == 1
    assert db.query(Alert).filter_by(sale_item_id=old["items"][0]["id"], status="VENCIDO_NO_GESTIONADO").count() == 1


def test_contact_attempt_validates_and_reprograms_inbox(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=15))
    client.post("/api/v1/alerts/generate", headers=supervisor_auth)
    alert = db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).one()
    advisor_auth = auth(client, advisor.email)
    invalid = client.post(f"/api/v1/alerts/{alert.id}/attempts", headers=advisor_auth, json={"channel": "LLAMADA", "result": "SIN_RESPUESTA"})
    assert invalid.status_code == 422
    result = client.post(f"/api/v1/alerts/{alert.id}/attempts", headers=advisor_auth, json={"channel": "WHATSAPP", "result": "AUN_TIENE_PRODUCTO", "next_action_date": str(date.today() + timedelta(days=3))})
    assert result.status_code == 200 and result.json()["status"] == "REPROGRAMADO"
    assert db.query(AlertContactAttempt).filter_by(alert_id=alert.id).count() == 1
    assert client.get("/api/v1/alerts/inbox", headers=advisor_auth).json()[0]["id"] == alert.id


def test_confirmed_repurchase_and_annulment_close_active_alerts(client: TestClient, db: Session) -> None:
    sale, product, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=15))
    client.post("/api/v1/alerts/generate", headers=supervisor_auth)
    first_alert = db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).one()
    advisor_auth = auth(client, advisor.email)
    repurchase = client.post("/api/v1/sales", headers=advisor_auth, json={"customer_id": sale["customer_id"], "sale_date": str(date.today()), "source_alert_id": first_alert.id, "items": [{"product_id": product["id"], "quantity": 1}]}).json()
    db.refresh(first_alert)
    assert first_alert.status == "RECOMPRA_LOGRADA"
    new_alert = Alert(sale_item_id=repurchase["items"][0]["id"], assigned_advisor_id=advisor.id, alert_date=date.today(), expected_repurchase_date=date.today() + timedelta(days=30))
    db.add(new_alert)
    db.commit()
    assert client.post(f"/api/v1/sales/{repurchase['id']}/annul", headers=supervisor_auth, json={"reason": "Venta anulada"}).status_code == 200
    db.refresh(new_alert)
    assert new_alert.status == "CANCELADO_POR_ANULACION"
