from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.alerts.models import Alert
from app.modules.supervision.models import AlertAssignmentHistory, CustomerAssignmentHistory
from tests.test_alerts import auth, make_user, setup_sale


def test_portfolio_transfer_moves_active_alerts_and_records_history(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, original_advisor = setup_sale(client, db, date.today() - timedelta(days=30))
    replacement = make_user(db, "replacement@example.com", "ASESOR")
    assert client.get("/api/v1/alerts/inbox", headers=supervisor_auth).status_code == 200
    response = client.post(
        f"/api/v1/supervision/customers/{sale['customer_id']}/transfer", headers=supervisor_auth,
        json={"assigned_advisor_id": replacement.id, "reason": "Coverage change"},
    )
    assert response.status_code == 200
    assert response.json()["transferred_alerts"] == 1
    alert = db.query(Alert).one()
    assert alert.assigned_advisor_id == replacement.id
    assert db.query(CustomerAssignmentHistory).count() == 1
    assert db.query(AlertAssignmentHistory).count() == 1
    assert client.post(f"/api/v1/alerts/{alert.id}/attempts", headers=auth(client, original_advisor.email), json={"channel": "LLAMADA", "result": "SIN_RESPUESTA", "next_action_date": str(date.today())}).status_code == 403


def test_recovery_queue_assigns_only_active_alerts(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, _ = setup_sale(client, db, date.today() - timedelta(days=30), suffix="queue")
    replacement = make_user(db, "queue-advisor@example.com", "ASESOR")
    client.get("/api/v1/alerts/inbox", headers=supervisor_auth)
    transfer = client.post(f"/api/v1/supervision/customers/{sale['customer_id']}/transfer", headers=supervisor_auth, json={"assigned_advisor_id": None, "reason": "Recovery queue"})
    assert transfer.status_code == 200
    queued = client.get("/api/v1/supervision/recovery-alerts", headers=supervisor_auth)
    assert len(queued.json()) == 1
    alert_id = queued.json()[0]["id"]
    assert client.post(f"/api/v1/supervision/alerts/{alert_id}/assign", headers=supervisor_auth, json={"assigned_advisor_id": replacement.id, "reason": "Assigned from queue"}).status_code == 200
    assert client.get("/api/v1/supervision/recovery-alerts", headers=supervisor_auth).json() == []


def test_reports_filter_invalid_alerts_and_export_csv(client: TestClient, db: Session) -> None:
    sale, _, supervisor_auth, _ = setup_sale(client, db, date.today() - timedelta(days=30), suffix="report")
    client.get("/api/v1/alerts/inbox", headers=supervisor_auth)
    reports = client.get("/api/v1/reports/sales", headers=supervisor_auth)
    assert reports.status_code == 200
    assert reports.json()["rows"][0]["confirmed_sales"] == 1
    assert reports.json()["rows"][0]["channel"] == "TV"
    csv_export = client.get("/api/v1/reports/alerts.csv", headers=supervisor_auth)
    assert csv_export.status_code == 200
    assert csv_export.headers["content-type"].startswith("text/csv")
    metrics = client.get("/api/v1/reports/metrics", headers=supervisor_auth)
    assert metrics.json()["alerts_considered"] == 1
    assert client.get("/api/v1/reports/sales", headers=auth(client, "advisor-alertreport@example.com")).status_code == 403


def test_recovery_pagination_and_bulk_assignment_are_audited(client: TestClient, db: Session) -> None:
    first, _, supervisor_auth, _ = setup_sale(client, db, date.today() - timedelta(days=30), suffix="bulkone")
    second, _, _, _ = setup_sale(client, db, date.today() - timedelta(days=30), suffix="bulktwo")
    target = make_user(db, "bulk-target@example.com", "ASESOR")
    client.get("/api/v1/alerts/inbox", headers=supervisor_auth)
    for sale in (first, second):
        assert client.post(
            f"/api/v1/supervision/customers/{sale['customer_id']}/transfer", headers=supervisor_auth,
            json={"assigned_advisor_id": None, "reason": "Queue for bulk assignment"},
        ).status_code == 200
    queue = client.get("/api/v1/supervision/recovery-queue?page=1&page_size=1", headers=supervisor_auth)
    assert queue.status_code == 200
    assert queue.json()["page"] == 1
    assert queue.json()["page_size"] == 1
    assert queue.json()["total"] == 2
    assert queue.json()["pages"] == 2
    alert_ids = [alert.id for alert in db.query(Alert).order_by(Alert.id)]
    assigned = client.post("/api/v1/supervision/alerts/bulk-assign", headers=supervisor_auth, json={
        "alert_ids": alert_ids, "assigned_advisor_id": target.id, "reason": "Campaign capacity",
    })
    assert assigned.status_code == 200
    assert assigned.json()["count"] == 2
    assert db.query(AlertAssignmentHistory).filter(AlertAssignmentHistory.assigned_advisor_id == target.id).count() == 2


def test_metrics_group_attempts_at_root_typification(client: TestClient, db: Session) -> None:
    _, _, supervisor_auth, advisor = setup_sale(client, db, date.today() - timedelta(days=30), suffix="metricroot")
    parent = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={"code": "ROOT_METRIC", "name": "Root metric"}).json()
    child = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={"code": "CHILD_METRIC", "name": "Child metric", "parent_id": parent["id"]}).json()
    alert = client.get("/api/v1/alerts/inbox", headers=supervisor_auth).json()[0]
    assert client.post(f"/api/v1/alerts/{alert['id']}/attempts", headers=auth(client, advisor.email), json={
        "channel": "LLAMADA", "result": child["code"], "typification_id": child["id"], "next_action_date": str(date.today()),
    }).status_code == 200
    metrics = client.get("/api/v1/reports/metrics", headers=supervisor_auth).json()
    assert metrics["repurchase_denominator"] == 1
    assert metrics["advisor_ranking"][0]["contact_attempts"] == 1
    assert metrics["attention_typifications"] == [{"typification_id": parent["id"], "typification_code": "ROOT_METRIC", "typification_name": "Root metric", "attempts": 1}]
