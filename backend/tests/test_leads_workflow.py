from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_alerts import auth, make_user


def test_lead_activity_uses_configured_leaf_outcome_and_board_filters(client: TestClient, db: Session) -> None:
    advisor = make_user(db, "lead-advisor@example.com", "ASESOR")
    supervisor = make_user(db, "lead-supervisor@example.com", "SUPERVISOR")
    advisor_auth = auth(client, advisor.email)
    supervisor_auth = auth(client, supervisor.email)
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
        "full_name": "Lead Scheduled", "phone": "999999999", "source": "REDES_SOCIALES",
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
    assert board.json()["total"] == 1
    assert board.json()["items"][0]["id"] == lead["id"]
    assert client.get("/api/v1/leads/board-summary", headers=advisor_auth).json()["AGENDADO"] == 1
    assert client.get("/api/v1/leads/board?status=AGENDADO&next_action=DUE", headers=advisor_auth).json()["total"] == 0
    assert client.post(f"/api/v1/leads/{lead['id']}/close", headers=advisor_auth, json={}).status_code == 404


def test_supervisor_bulk_reassigns_recoverable_leads(client: TestClient, db: Session) -> None:
    advisor = make_user(db, "bulk-lead-advisor@example.com", "ASESOR")
    replacement = make_user(db, "bulk-lead-replacement@example.com", "ASESOR")
    supervisor = make_user(db, "bulk-lead-supervisor@example.com", "SUPERVISOR")
    advisor_auth = auth(client, advisor.email)
    supervisor_auth = auth(client, supervisor.email)
    typification = client.post("/api/v1/configuration/contact-typifications", headers=supervisor_auth, json={
        "code": "BULK_RECOVERY", "name": "Bulk recovery", "lead_outcome": "RECUPERABLE",
    }).json()
    lead = client.post("/api/v1/leads", headers=advisor_auth, json={
        "full_name": "Recovery Lead", "phone": "988888888", "source": "REFERIDO",
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
