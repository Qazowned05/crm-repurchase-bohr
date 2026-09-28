from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.alerts.models import Alert
from app.modules.audit.models import AuditLog
from tests.test_alerts import auth, setup_sale


def test_configured_typification_is_validated_and_audited(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=15))
    created = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={
        "code": " CALL_BACK ", "name": "Call back", "requires_next_action": True, "requires_note": True,
    })
    assert created.status_code == 201
    typification = created.json()
    assert typification["code"] == "CALL_BACK"
    assert client.patch(f"/api/v1/configuration/contact-typifications/{typification['id']}", headers=supervisor_auth, json={"is_active": False}).status_code == 200
    client.post("/api/v1/alerts/generate", headers=supervisor_auth)
    alert = db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).one()
    advisor_auth = auth(client, advisor.email)
    assert client.post(f"/api/v1/alerts/{alert.id}/attempts", headers=advisor_auth, json={"channel": "LLAMADA", "result": "CALL_BACK"}).status_code == 422
    assert client.patch(f"/api/v1/configuration/contact-typifications/{typification['id']}", headers=supervisor_auth, json={"is_active": True}).status_code == 200
    assert client.post(f"/api/v1/alerts/{alert.id}/attempts", headers=advisor_auth, json={"channel": "LLAMADA", "result": "CALL_BACK", "note": "Requested call", "next_action_date": str(date.today())}).status_code == 200
    assert db.query(AuditLog).filter_by(entity_type="contact_typification", action="CREATED").count() == 1


def test_settings_drive_grouped_recovery_queue(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=15))
    assert client.put("/api/v1/configuration/alert-settings", headers=supervisor_auth, json={"advisor_visibility_days": 30, "maximum_attempts": 1, "stale_days": 30}).status_code == 200
    client.post("/api/v1/alerts/generate", headers=supervisor_auth)
    first = db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).one()
    second = Alert(sale_item_id=first.sale_item_id, assigned_advisor_id=None, alert_date=first.alert_date + timedelta(days=1), expected_repurchase_date=first.expected_repurchase_date)
    first.attempts_count = 1
    db.add(second)
    db.commit()

    advisor_auth = auth(client, advisor.email)
    assert client.get("/api/v1/alerts/inbox", headers=advisor_auth).json() == []
    queue = client.get("/api/v1/supervision/recovery-queue", headers=supervisor_auth)
    assert queue.status_code == 200
    assert len(queue.json()) == 1
    assert {alert["id"] for alert in queue.json()[0]["alerts"]} == {first.id, second.id}
    assert db.query(AuditLog).filter_by(entity_type="alert_operational_settings", action="UPDATED").count() == 1
