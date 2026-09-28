from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.auth.models import User
from app.modules.configuration.models import AlertOperationalSettings, ContactTypification
from app.modules.customers.models import Customer
from app.modules.products.models import Brand, Product, ProductCategory, ProductRepurchaseRule
from app.modules.sales.models import Sale, SaleItem
from app.modules.supervision.models import AlertAssignmentHistory, CustomerAssignmentHistory
from app.scripts.reset_and_seed_demo import EXPECTED_COUNTS, active_advisors, seed_demo_45


def count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_demo_45_seed_uses_valid_model_fields_and_expected_counts(db: Session) -> None:
    db.add_all([
        User(email=f"advisor{number}@example.test", password_hash="test", full_name=f"Advisor {number}", role="ASESOR", is_active=True)
        for number in range(1, 4)
    ])
    db.commit()

    seed_demo_45(db, active_advisors(db), date.today())
    db.commit()

    assert count(db, Customer) == EXPECTED_COUNTS["customers"]
    assert count(db, Brand) == EXPECTED_COUNTS["brands"]
    assert count(db, ProductCategory) == EXPECTED_COUNTS["product_categories"]
    assert count(db, Product) == EXPECTED_COUNTS["products"]
    assert count(db, ProductRepurchaseRule) == EXPECTED_COUNTS["product_repurchase_rules"]
    assert count(db, ContactTypification) == EXPECTED_COUNTS["contact_typifications"]
    assert count(db, AlertOperationalSettings) == EXPECTED_COUNTS["alert_operational_settings"]
    assert count(db, Sale) == EXPECTED_COUNTS["confirmed_sales_total"]
    assert count(db, SaleItem) == EXPECTED_COUNTS["sale_items"]
    assert count(db, Alert) == EXPECTED_COUNTS["alerts"]
    assert count(db, AlertContactAttempt) == EXPECTED_COUNTS["alert_contact_attempts"]
    assert count(db, CustomerAssignmentHistory) == EXPECTED_COUNTS["customer_assignment_history"]
    assert count(db, AlertAssignmentHistory) == EXPECTED_COUNTS["alert_assignment_history"]
    assert count(db, Alert) == 45 * 5
    assert count(db, AlertContactAttempt) == 45 * 3
    assert count(db, Sale) == 225 + 45
    assert count(db, Sale) == db.scalar(select(func.count()).select_from(Sale).where(Sale.status == "CONFIRMADA"))
    assert db.scalar(select(func.count()).select_from(Sale).where(Sale.source_alert_id.is_not(None))) == 45
    assert db.scalar(select(func.count()).select_from(SaleItem).where(SaleItem.purchase_type == "RECOMPRA")) == 45
    assert count(db, Alert) == db.scalar(select(func.count()).select_from(Alert).where(Alert.status.in_({
        "PENDIENTE", "VENCIDO_NO_GESTIONADO", "REPROGRAMADO", "CERRADO_POR_TIPIFICACION", "RECOMPRA_LOGRADA",
    })))
    for status in ("PENDIENTE", "VENCIDO_NO_GESTIONADO", "REPROGRAMADO", "CERRADO_POR_TIPIFICACION", "RECOMPRA_LOGRADA"):
        assert db.scalar(select(func.count()).select_from(Alert).where(Alert.status == status)) == 45
