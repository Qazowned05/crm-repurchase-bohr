"""configure lead outcomes for the existing demo typifications

Revision ID: 0026_seed_lead_outcomes
Revises: 0025_typif_lead_outcome
"""
from collections.abc import Sequence

from alembic import op


revision: str = "0026_seed_lead_outcomes"
down_revision: str | None = "0025_typif_lead_outcome"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    outcomes = {
        "SOLICITA_LLAMADA": "AGENDADO",
        "SIN_RESPUESTA": "RECUPERABLE",
        "NO_INTERESADO": "NO_RECUPERABLE",
        "PEDIDO_CONFIRMADO": "EFECTIVO",
    }
    for code, outcome in outcomes.items():
        op.execute(
            f"UPDATE contact_typifications SET lead_outcome = '{outcome}' "
            f"WHERE code = '{code}' AND lead_outcome IS NULL"
        )


def downgrade() -> None:
    pass
