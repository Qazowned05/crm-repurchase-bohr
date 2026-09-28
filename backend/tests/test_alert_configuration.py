from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.alerts.models import Alert
from app.modules.audit.models import AuditLog
from tests.test_alerts import auth, setup_sale


def test_configured_typification_is_validated_and_audited(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30))
    created = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={
        "code": " CALL_BACK ", "name": "Call back", "requires_next_action": True, "requires_note": True,
    })
    assert created.status_code == 201
    typification = created.json()
    assert typification["code"] == "CALL_BACK"
    assert client.patch(f"/api/v1/configuration/contact-typifications/{typification['id']}", headers=supervisor_auth, json={"is_active": False}).status_code == 200
    client.get("/api/v1/alerts/inbox", headers=supervisor_auth)
    alert = db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).one()
    advisor_auth = auth(client, advisor.email)
    assert client.post(f"/api/v1/alerts/{alert.id}/attempts", headers=advisor_auth, json={"channel": "LLAMADA", "result": "CALL_BACK"}).status_code == 422
    assert client.patch(f"/api/v1/configuration/contact-typifications/{typification['id']}", headers=supervisor_auth, json={"is_active": True}).status_code == 200
    assert client.post(f"/api/v1/alerts/{alert.id}/attempts", headers=advisor_auth, json={"channel": "LLAMADA", "result": "CALL_BACK", "note": "Requested call", "next_action_date": str(date.today())}).status_code == 200
    assert db.query(AuditLog).filter_by(entity_type="contact_typification", action="CREATED").count() == 1


def test_settings_drive_grouped_recovery_queue(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30))
    assert client.put("/api/v1/configuration/alert-settings", headers=supervisor_auth, json={"advisor_visibility_days": 30, "maximum_attempts": 1, "stale_days": 30}).status_code == 200
    client.get("/api/v1/alerts/inbox", headers=supervisor_auth)
    first = db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).one()
    first.attempts_count = 1
    db.commit()

    advisor_auth = auth(client, advisor.email)
    assert client.get("/api/v1/alerts/inbox", headers=advisor_auth).json() == []
    queue = client.get("/api/v1/supervision/recovery-queue", headers=supervisor_auth)
    assert queue.status_code == 200
    assert len(queue.json()) == 1
    assert {alert["id"] for alert in queue.json()[0]["alerts"]} == {first.id}
    assert db.query(AuditLog).filter_by(entity_type="alert_operational_settings", action="UPDATED").count() == 1


def test_typification_tree_prevents_cycles_and_deletion_with_children_or_references(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30), suffix="tree")
    parent = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={"code": "CONTACTED", "name": "Contacted"})
    assert parent.status_code == 201
    child = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={"code": "CONTACTED_CALL", "name": "Contacted by call", "parent_id": parent.json()["id"]})
    assert child.status_code == 201
    tree = client.get("/api/v1/configuration/contact-typifications/tree", headers=supervisor_auth)
    assert tree.status_code == 200
    assert tree.json()[0]["children"][0]["code"] == "CONTACTED_CALL"
    assert client.patch(f"/api/v1/configuration/contact-typifications/{parent.json()['id']}", headers=supervisor_auth, json={"parent_id": child.json()["id"]}).status_code == 422
    assert client.delete(f"/api/v1/configuration/contact-typifications/{parent.json()['id']}", headers=supervisor_auth).status_code == 409
    client.get("/api/v1/alerts/inbox", headers=supervisor_auth)
    alert = db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).one()
    assert client.post(f"/api/v1/alerts/{alert.id}/attempts", headers=auth(client, advisor.email), json={"channel": "LLAMADA", "result": "CONTACTED_CALL"}).status_code == 200
    assert client.delete(f"/api/v1/configuration/contact-typifications/{child.json()['id']}", headers=supervisor_auth).status_code == 409


def test_recovery_queue_filters_latest_descendant_typification_and_days_overdue(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30), suffix="filter")
    parent = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={"code": "FOLLOW_UP", "name": "Follow up"}).json()
    child = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={"code": "FOLLOW_UP_CALL", "name": "Follow up call", "parent_id": parent["id"]}).json()
    assert client.put("/api/v1/configuration/alert-settings", headers=supervisor_auth, json={"advisor_visibility_days": 30, "maximum_attempts": 1, "stale_days": 30}).status_code == 200
    client.get("/api/v1/alerts/inbox", headers=supervisor_auth)
    alert = db.query(Alert).filter_by(sale_item_id=sale["items"][0]["id"]).one()
    assert client.post(f"/api/v1/alerts/{alert.id}/attempts", headers=auth(client, advisor.email), json={"channel": "LLAMADA", "result": child["code"]}).status_code == 200
    queue = client.get(f"/api/v1/supervision/recovery-queue?typification_id={parent['id']}&min_days_overdue=0&max_days_overdue=0", headers=supervisor_auth)
    assert queue.status_code == 200
    queued_alert = queue.json()[0]["alerts"][0]
    assert queued_alert["id"] == alert.id
    assert queued_alert["latest_contact_typification"] == child["code"]
    assert queued_alert["latest_contact_date"] is not None
    assert client.get(f"/api/v1/supervision/recovery-queue?typification_id={parent['id']}&min_days_overdue=1", headers=supervisor_auth).json() == []
