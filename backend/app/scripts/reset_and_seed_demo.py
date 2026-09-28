"""Reset operational data and seed a deterministic demo dataset.

Run from the backend directory:
    python -m app.scripts.reset_and_seed_demo
    python -m app.scripts.reset_and_seed_demo --confirm-delete-operational-data

The first command is intentionally a dry run.  Users and Alembic's version
table are never changed by this script.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.audit.models import AuditLog
from app.modules.auth.models import PasswordResetToken, User
from app.modules.configuration.models import AlertOperationalSettings, ContactTypification
from app.modules.customers.models import Customer
from app.modules.imports.models import ImportJob, ImportRowError
from app.modules.products.models import Brand, Product, ProductCategory, ProductRepurchaseRule
from app.modules.sales.models import Sale, SaleDuplicateReview, SaleItem
from app.modules.supervision.models import AlertAssignmentHistory, CustomerAssignmentHistory


PROFILE = "demo-45"
ADVISORY_LOCK_ID = 45_202_609_28
CUSTOMERS_PER_ADVISOR = 75
GROUP_SIZE = 45
RULE_DURATION_DAYS = 60
RULE_ALERT_DAYS = [14, 7]

EXPECTED_COUNTS = {
    "customers": 225,
    "brands": 9,
    "product_categories": 5,
    "products": 45,
    "product_repurchase_rules": 45,
    "contact_typifications": 6,
    "alert_operational_settings": 1,
    "original_confirmed_sales": 225,
    "ensuing_repurchase_sales": 45,
    "confirmed_sales_total": 270,
    "sale_items": 270,
    "alerts": 225,
    "alert_contact_attempts": 135,
    "customer_assignment_history": 225,
    "alert_assignment_history": 225,
}


def active_advisors(db: Session) -> list[User]:
    advisors = list(db.scalars(
        select(User).where(User.role == "ASESOR", User.is_active.is_(True)).order_by(User.email)
    ))
    if len(advisors) != 3:
        raise RuntimeError(
            f"{PROFILE} requires exactly 3 active ASESOR users; found {len(advisors)}. "
            "Users are preserved, so correct users before running this script."
        )
    return advisors


def acquire_transaction_lock(db: Session) -> None:
    if db.bind is None or db.bind.dialect.name != "postgresql":
        raise RuntimeError("This destructive demo reset requires PostgreSQL for its transaction advisory lock.")
    db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": ADVISORY_LOCK_ID})


def delete_operational_data(db: Session) -> None:
    """Delete every mapped non-user table in foreign-key-safe order."""
    # Sales points at alerts through source_alert_id, so clear that nullable edge first.
    db.execute(text("UPDATE sales SET source_alert_id = NULL WHERE source_alert_id IS NOT NULL"))
    for model in (
        PasswordResetToken,
        ImportRowError,
        ImportJob,
        AlertContactAttempt,
        AlertAssignmentHistory,
        CustomerAssignmentHistory,
        SaleDuplicateReview,
        Alert,
        AuditLog,
        SaleItem,
        Sale,
        ProductRepurchaseRule,
        Product,
        Brand,
        ProductCategory,
        ContactTypification,
        AlertOperationalSettings,
        Customer,
    ):
        db.execute(delete(model))
    db.flush()


def seed_demo_45(db: Session, advisors: list[User], today: date) -> None:
    now = datetime.now(timezone.utc)
    actor = advisors[0]
    brands = [Brand(name=f"Demo Brand {number:02d}", is_active=True) for number in range(1, 10)]
    categories = [ProductCategory(name=f"Demo Category {number:02d}", is_active=True) for number in range(1, 6)]
    db.add_all(brands + categories)
    db.flush()

    products = [
        Product(
            code=f"DEMO-{number:03d}",
            name=f"Demo Product {number:02d}",
            brand_id=brands[(number - 1) % len(brands)].id,
            category_id=categories[(number - 1) % len(categories)].id,
            is_active=True,
        )
        for number in range(1, 46)
    ]
    db.add_all(products)
    db.flush()
    db.add_all([
        ProductRepurchaseRule(
            product_id=product.id,
            duration_days=RULE_DURATION_DAYS,
            alert_days=RULE_ALERT_DAYS,
            effective_from=today - timedelta(days=365),
            created_by_user_id=actor.id,
        )
        for product in products
    ])

    follow_up = ContactTypification(code="SEGUIMIENTO", name="Seguimiento", is_active=True)
    follow_up_child = ContactTypification(
        parent_id=None, code="SOLICITA_SEGUIMIENTO", name="Solicita seguimiento",
        is_active=True, requires_next_action=True,
    )
    close = ContactTypification(code="CIERRE", name="Cierre", is_active=True)
    close_child = ContactTypification(
        parent_id=None, code="CIERRE_DEFINITIVO", name="Cierre definitivo",
        is_active=True, requires_close=True, requires_note=True,
    )
    repurchase = ContactTypification(code="RECOMPRA", name="Recompra", is_active=True)
    repurchase_child = ContactTypification(
        parent_id=None, code="RECOMPRA_REGISTRADA", name="Recompra registrada", is_active=True,
    )
    roots = [follow_up, close, repurchase]
    db.add_all(roots)
    db.flush()
    follow_up_child.parent_id = follow_up.id
    close_child.parent_id = close.id
    repurchase_child.parent_id = repurchase.id
    db.add_all([follow_up_child, close_child, repurchase_child])
    db.add(AlertOperationalSettings(id=1, advisor_visibility_days=30, maximum_attempts=3, stale_days=7))

    customers: list[Customer] = []
    for number in range(1, 226):
        advisor = advisors[(number - 1) // CUSTOMERS_PER_ADVISOR]
        customers.append(Customer(
            dni=f"D{number:08d}", first_names=f"Demo{number:03d}", last_names=f"Customer{number:03d}",
            phone=f"+519{number:08d}", email=f"demo{number:03d}@example.test", status="ACTIVO",
            responsible_advisor_id=advisor.id, acquisition_channel="DEMO", acquisition_channel_detail=PROFILE,
            condition="Demo customer", birth_year=1980 + (number % 25), sales_district=f"District {(number - 1) % 5 + 1}",
        ))
    db.add_all(customers)
    db.flush()
    db.add_all([
        CustomerAssignmentHistory(
            customer_id=customer.id, previous_advisor_id=None, assigned_advisor_id=customer.responsible_advisor_id,
            reason=f"{PROFILE} initial portfolio assignment", assigned_by_user_id=actor.id, created_at=now,
        )
        for customer in customers
    ])

    original_sales: list[Sale] = []
    # These dates deliberately produce: current, expired recovery, reprogrammed, closed, and repurchased groups.
    sale_dates = ([today - timedelta(days=RULE_DURATION_DAYS)] * GROUP_SIZE
                  + [today - timedelta(days=RULE_DURATION_DAYS + 40)] * GROUP_SIZE
                  + [today - timedelta(days=RULE_DURATION_DAYS + 5)] * GROUP_SIZE
                  + [today - timedelta(days=RULE_DURATION_DAYS + 10)] * GROUP_SIZE
                  + [today - timedelta(days=RULE_DURATION_DAYS + 2)] * GROUP_SIZE)
    for number, (customer, sale_date) in enumerate(zip(customers, sale_dates), start=1):
        original_sales.append(Sale(
            customer_id=customer.id, advisor_id=customer.responsible_advisor_id, sale_date=sale_date,
            notes=f"{PROFILE} original sale {number}", status="CONFIRMADA", acquisition_channel="DEMO",
            acquisition_channel_detail=PROFILE,
        ))
    db.add_all(original_sales)
    db.flush()
    original_items = [
        SaleItem(
            sale_id=sale.id, product_id=products[(number - 1) % len(products)].id, quantity=1,
            rule_duration_days=RULE_DURATION_DAYS, rule_alert_days=RULE_ALERT_DAYS,
            expected_repurchase_date=sale.sale_date + timedelta(days=RULE_DURATION_DAYS), purchase_type="COMPRA",
        )
        for number, sale in enumerate(original_sales, start=1)
    ]
    db.add_all(original_items)
    db.flush()

    alerts: list[Alert] = []
    for number, (sale, item) in enumerate(zip(original_sales, original_items), start=1):
        group = (number - 1) // GROUP_SIZE
        alert_date = item.expected_repurchase_date
        values = {
            "sale_item_id": item.id,
            "assigned_advisor_id": sale.advisor_id,
            "alert_date": alert_date,
            "expected_repurchase_date": alert_date,
            "status": "PENDIENTE",
        }
        if group == 1:
            values.update(status="VENCIDO_NO_GESTIONADO", closed_at=now, closure_reason="VENCIDA_SIN_GESTION")
        elif group == 2:
            values.update(status="REPROGRAMADO", attempts_count=1, last_contact_at=now - timedelta(days=1), next_action_date=today + timedelta(days=3))
        elif group == 3:
            values.update(status="CERRADO_POR_TIPIFICACION", attempts_count=1, last_contact_at=now - timedelta(days=2), closed_at=now - timedelta(days=2), closure_reason="TIPIFICACION_DE_CIERRE: Cierre definitivo")
        elif group == 4:
            values.update(status="RECOMPRA_LOGRADA", attempts_count=1, last_contact_at=now - timedelta(days=1), closed_at=now - timedelta(days=1), closure_reason="RECOMPRA_CONFIRMADA")
        alerts.append(Alert(**values))
    db.add_all(alerts)
    db.flush()
    db.add_all([
        AlertAssignmentHistory(
            alert_id=alert.id, previous_advisor_id=None, assigned_advisor_id=alert.assigned_advisor_id,
            reason=f"{PROFILE} initial alert assignment", assigned_by_user_id=actor.id, created_at=now,
        )
        for alert in alerts
    ])

    attempts: list[AlertContactAttempt] = []
    for offset in range(GROUP_SIZE):
        managed_alert = alerts[2 * GROUP_SIZE + offset]
        closed_alert = alerts[3 * GROUP_SIZE + offset]
        repurchase_alert = alerts[4 * GROUP_SIZE + offset]
        attempts.extend([
            AlertContactAttempt(alert_id=managed_alert.id, advisor_id=managed_alert.assigned_advisor_id,
                                contacted_at=now - timedelta(days=1), channel="WHATSAPP", result=follow_up_child.code,
                                typification_id=follow_up_child.id, note="Customer requested a follow-up.",
                                next_action_date=managed_alert.next_action_date),
            AlertContactAttempt(alert_id=closed_alert.id, advisor_id=closed_alert.assigned_advisor_id,
                                contacted_at=now - timedelta(days=2), channel="LLAMADA", result=close_child.code,
                                typification_id=close_child.id, note="Customer confirmed definitive closure."),
            AlertContactAttempt(alert_id=repurchase_alert.id, advisor_id=repurchase_alert.assigned_advisor_id,
                                contacted_at=now - timedelta(days=1), channel="LLAMADA", result=repurchase_child.code,
                                typification_id=repurchase_child.id, note="Confirmed repurchase recorded."),
        ])
    db.add_all(attempts)

    repurchase_sales: list[Sale] = []
    for offset in range(GROUP_SIZE):
        original_sale = original_sales[4 * GROUP_SIZE + offset]
        repurchase_sales.append(Sale(
            customer_id=original_sale.customer_id, advisor_id=original_sale.advisor_id, sale_date=today - timedelta(days=1),
            notes=f"{PROFILE} repurchase from alert", status="CONFIRMADA", acquisition_channel="DEMO",
            acquisition_channel_detail=PROFILE, source_alert_id=alerts[4 * GROUP_SIZE + offset].id,
        ))
    db.add_all(repurchase_sales)
    db.flush()
    db.add_all([
        SaleItem(
            sale_id=sale.id, product_id=original_items[4 * GROUP_SIZE + offset].product_id, quantity=1,
            rule_duration_days=RULE_DURATION_DAYS, rule_alert_days=RULE_ALERT_DAYS,
            expected_repurchase_date=sale.sale_date + timedelta(days=RULE_DURATION_DAYS), purchase_type="RECOMPRA",
            prior_confirmed_item_id=original_items[4 * GROUP_SIZE + offset].id,
        )
        for offset, sale in enumerate(repurchase_sales)
    ])
    db.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset operational data and seed the demo-45 dataset.")
    parser.add_argument("--profile", choices=[PROFILE], default=PROFILE, help="Demo dataset to seed (default: demo-45).")
    parser.add_argument("--confirm-delete-operational-data", action="store_true", help="Actually delete operational/configuration data and seed the profile.")
    return parser.parse_args()


def print_summary(dry_run: bool, advisors: list[User]) -> None:
    mode = "DRY RUN: no data was changed" if dry_run else "SEEDED"
    print(f"{mode} profile={PROFILE}")
    print("active advisors=" + ", ".join(advisor.email for advisor in advisors))
    print("expected counts:")
    for name, count in EXPECTED_COUNTS.items():
        print(f"  {name}: {count}")


def main() -> None:
    args = parse_args()
    with SessionLocal() as db:
        with db.begin():
            acquire_transaction_lock(db)
            advisors = active_advisors(db)
            if args.confirm_delete_operational_data:
                delete_operational_data(db)
                seed_demo_45(db, advisors, date.today())
        print_summary(not args.confirm_delete_operational_data, advisors)


if __name__ == "__main__":
    main()
