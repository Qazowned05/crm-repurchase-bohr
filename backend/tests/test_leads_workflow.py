from datetime import datetime, timedelta, timezone
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from tests.test_alerts import auth, make_user, setup_sale


def test_lead_activity_uses_configured_leaf_outcome_and_board_filters(client: TestClient, db: Session) -> None:
    advisor = make_user(db, "lead-advisor@example.com", "ASESOR")
    supervisor = make_user(db, "lead-supervisor@example.com", "SUPERVISOR")
    advisor_auth = auth(client, advisor.email)
    supervisor_auth = auth(client, supervisor.email)
    campaign = client.post("/api/v1/campaigns", headers=supervisor_auth, json={"name": "Social"}).json()
    parent = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={
        "code": "FOLLOWUP", "name": "Follow up", "lead_outcome": "PENDIENTE",
    }).json()
    deprecated_outcome = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={
        "code": "NO_RECOVERY", "name": "No recovery", "lead_outcome": "NO_RECUPERABLE",
    })
    assert deprecated_outcome.status_code == 422
    scheduled = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={
        "code": "FOLLOWUP_SCHEDULED", "name": "Scheduled", "parent_id": parent["id"], "lead_outcome": "AGENDADO",
    }).json()
    lead = client.post("/api/v1/leads", headers=advisor_auth, json={
        "full_name": "Lead Scheduled", "phone": "999999999", "campaign_id": campaign["id"],
    }).json()

    assert client.post(f"/api/v1/leads/{lead['id']}/activities", headers=advisor_auth, json={
        "channel": "LLAMADA", "typification_id": parent["id"],
    }).status_code == 422
    missing_schedule = client.post(f"/api/v1/leads/{lead['id']}/activities", headers=advisor_auth, json={
        "channel": "LLAMADA", "typification_id": scheduled["id"],
    })
    assert missing_schedule.status_code == 422

    action_at = datetime.now(timezone.utc) + timedelta(days=1)
    recorded = client.post(f"/api/v1/leads/{lead['id']}/activities", headers=advisor_auth, json={
        "channel": "LLAMADA", "typification_id": scheduled["id"],
        "next_action_date": str(action_at.date()), "next_action_at": action_at.isoformat(),
    })
    assert recorded.status_code == 200
    assert recorded.json()["status"] == "AGENDADO"
    assert recorded.json()["latest_typification_id"] == scheduled["id"]

    board = client.get(f"/api/v1/leads/board?status=AGENDADO&typification_id={scheduled['id']}", headers=advisor_auth)
    assert board.status_code == 200
    assert board.json()["total"] == 0
    assert board.json()["items"] == []
    assert client.get("/api/v1/leads/board-summary", headers=advisor_auth).json()["AGENDADO"] == 0
    assert client.get("/api/v1/leads/board?status=AGENDADO&next_action=DUE", headers=advisor_auth).json()["total"] == 0
    assert client.post(f"/api/v1/leads/{lead['id']}/close", headers=advisor_auth, json={}).status_code == 404


def test_supervisor_bulk_reassigns_recoverable_leads(client: TestClient, db: Session) -> None:
    advisor = make_user(db, "bulk-lead-advisor@example.com", "ASESOR")
    replacement = make_user(db, "bulk-lead-replacement@example.com", "ASESOR")
    supervisor = make_user(db, "bulk-lead-supervisor@example.com", "SUPERVISOR")
    advisor_auth = auth(client, advisor.email)
    supervisor_auth = auth(client, supervisor.email)
    campaign = client.post("/api/v1/campaigns", headers=supervisor_auth, json={"name": "Referidos"}).json()
    typification = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={
        "code": "BULK_RECOVERY", "name": "Bulk recovery", "lead_outcome": "RECUPERABLE",
    }).json()
    lead = client.post("/api/v1/leads", headers=advisor_auth, json={
        "full_name": "Recovery Lead", "phone": "988888888", "campaign_id": campaign["id"],
    }).json()
    assert client.post(f"/api/v1/leads/{lead['id']}/activities", headers=advisor_auth, json={
        "channel": "LLAMADA", "typification_id": typification["id"],
    }).status_code == 200
    assigned = client.post("/api/v1/leads/bulk-assign", headers=supervisor_auth, json={
        "lead_ids": [lead["id"]], "assigned_advisor_id": replacement.id, "reason": "Redistribución",
    })
    assert assigned.status_code == 200
    assert assigned.json()["count"] == 1
    updated = client.get(f"/api/v1/leads/{lead['id']}", headers=supervisor_auth).json()
    assert updated["assigned_advisor_id"] == replacement.id
    assert updated["status"] == "PENDIENTE"
    assert updated["reassigned_from_recovery"] is True
    assert updated["reassigned_at"] is not None
    assert client.get("/api/v1/leads/recovery", headers=supervisor_auth).json() == []


def test_supervisor_reassigns_leads_from_exported_workbook(client: TestClient, db: Session) -> None:
    advisor = make_user(db, "excel-lead-advisor@example.com", "ASESOR")
    replacement = make_user(db, "excel-lead-replacement@example.com", "ASESOR")
    supervisor = make_user(db, "excel-lead-supervisor@example.com", "SUPERVISOR")
    supervisor_auth = auth(client, supervisor.email)
    campaign = client.post("/api/v1/campaigns", headers=supervisor_auth, json={"name": "Excel Leads"}).json()
    lead = client.post("/api/v1/leads", headers=auth(client, advisor.email), json={
        "full_name": "Lead Excel", "phone": "955123456", "campaign_id": campaign["id"],
    }).json()

    exported = client.get("/api/v1/leads/assignment.xlsx?q=Lead%20Excel", headers=supervisor_auth)
    assert exported.status_code == 200
    workbook = load_workbook(BytesIO(exported.content))
    sheet = workbook["Data"]
    assert [cell.value for cell in sheet[1]] == ["lead_id", "full_name", "phone", "campaign", "status", "current_advisor_email", "responsible_advisor_email"]
    assert workbook["Asesores"].sheet_state == "hidden"
    assert sheet.data_validations.dataValidation[0].formula1 == "active_advisor_emails"
    assert sheet.cell(2, 1).value == lead["id"]
    sheet.cell(2, 7).value = replacement.email
    payload = BytesIO(); workbook.save(payload)

    imported = client.post(
        "/api/v1/leads/assignments/import",
        headers=supervisor_auth,
        files={"file": ("asignacion_leads.xlsx", payload.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert imported.status_code == 200
    assert imported.json() == {"processed": 1, "reassigned": 1}
    assert client.get(f"/api/v1/leads/{lead['id']}", headers=supervisor_auth).json()["assigned_advisor_id"] == replacement.id


def test_campaigns_are_managed_by_supervisors_and_inactive_campaigns_cannot_receive_leads(client: TestClient, db: Session) -> None:
    supervisor = make_user(db, "campaign-supervisor@example.com", "SUPERVISOR")
    advisor = make_user(db, "campaign-advisor@example.com", "ASESOR")
    supervisor_auth = auth(client, supervisor.email)
    campaign = client.post("/api/v1/campaigns", headers=supervisor_auth, json={"name": "Lanzamiento 2026"})
    assert campaign.status_code == 201
    campaign_id = campaign.json()["id"]
    assert client.patch(f"/api/v1/campaigns/{campaign_id}", headers=supervisor_auth, json={"is_active": False}).status_code == 200
    rejected = client.post("/api/v1/leads", headers=auth(client, advisor.email), json={
        "full_name": "Lead sin campaña activa", "phone": "977777777", "campaign_id": campaign_id,
    })
    assert rejected.status_code == 422


def test_assigned_advisor_can_enrich_lead_and_changes_are_audited(client: TestClient, db: Session) -> None:
    advisor = make_user(db, "enrich-advisor@example.com", "ASESOR")
    other_advisor = make_user(db, "other-enrich-advisor@example.com", "ASESOR")
    supervisor = make_user(db, "enrich-supervisor@example.com", "SUPERVISOR")
    supervisor_auth = auth(client, supervisor.email)
    campaign = client.post("/api/v1/campaigns", headers=supervisor_auth, json={"name": "Enrichment"}).json()
    _, product, _, _ = setup_sale(client, db, datetime.now(timezone.utc).date(), suffix="enrich")
    lead = client.post("/api/v1/leads", headers=auth(client, advisor.email), json={
        "phone": "955555555", "campaign_id": campaign["id"],
    }).json()

    updated = client.patch(f"/api/v1/leads/{lead['id']}", headers=auth(client, advisor.email), json={
        "full_name": "  Ana Lead  ", "phone": "966666666", "email": "ANA@EXAMPLE.COM",
        "condition": "  Hipertension  ", "notes": "  Prefiere WhatsApp  ", "initial_product_id": product["id"],
    })
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Ana Lead"
    assert updated.json()["email"] == "ana@example.com"
    assert updated.json()["condition"] == "Hipertension"
    assert updated.json()["notes"] == "Prefiere WhatsApp"
    assert updated.json()["initial_product_id"] == product["id"]
    assert client.patch(f"/api/v1/leads/{lead['id']}", headers=auth(client, other_advisor.email), json={"notes": "No autorizado"}).status_code == 403
    audit = db.query(AuditLog).filter_by(entity_type="lead", entity_id=lead["id"], action="UPDATED").one()
    assert audit.after_data["condition"] == "Hipertension"


def test_leads_only_typifications_are_hidden_from_alerts(client: TestClient, db: Session) -> None:
    supervisor = make_user(db, "scope-supervisor@example.com", "SUPERVISOR")
    supervisor_auth = auth(client, supervisor.email)
    lead_only = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={
        "code": "LEADS_ONLY_EFFECTIVE", "name": "Pedido de recompra confirmado", "lead_outcome": "EFECTIVO", "scope": "LEADS_ONLY",
    }).json()
    shared = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={
        "code": "SHARED", "name": "Shared",
    }).json()
    alert_tree = client.get("/api/v1/configuration/contact-typifications/tree?flow=ALERTS", headers=supervisor_auth).json()
    assert {item["id"] for item in alert_tree} == {shared["id"]}
    lead_tree = client.get("/api/v1/configuration/contact-typifications/tree?flow=LEADS", headers=supervisor_auth).json()
    assert {item["id"] for item in lead_tree} == {lead_only["id"], shared["id"]}
