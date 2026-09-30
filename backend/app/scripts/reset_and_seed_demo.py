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
from decimal import Decimal

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
REASSIGNED_ALERTS = 20
NO_RESPONSE_ALERTS = 10
RULE_DURATION_DAYS = 60
RULE_ALERT_DAYS = [14, 7]

EXPECTED_COUNTS = {
    "customers": 225,
    "brands": 9,
    "product_categories": 5,
    "products": 45,
    "product_repurchase_rules": 45,
    "contact_typifications": 8,
    "alert_operational_settings": 1,
    "original_confirmed_sales": 225,
    "ensuing_repurchase_sales": 45,
    "confirmed_sales_total": 270,
    "sale_items": 270,
    "alerts": 225,
    "alert_contact_attempts": 115,
    "customer_assignment_history": 225,
    "alert_assignment_history": 245,
}


def active_advisors(db: Session) -> list[User]:
    advisors = list(db.scalars(
        select(User).where(User.role == "ASESOR", User.is_active.is_(True)).order_by(User.email)
    ))
    if not advisors:
        raise RuntimeError(
            f"{PROFILE} requires at least one active ASESOR user; found {len(advisors)}. "
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
    brand_names = ["Nature's Bounty", "Centrum", "Ensure", "Vicks", "Bayer", "La Roche-Posay", "PediaSure", "GNC", "Kirkland Signature"]
    category_names = ["Vitaminas y suplementos", "Nutrición especializada", "Salud respiratoria", "Cuidado personal", "Bienestar y movilidad"]
    brands = [Brand(name=name, is_active=True) for name in brand_names]
    categories = [ProductCategory(name=name, is_active=True) for name in category_names]
    db.add_all(brands + categories)
    db.flush()

    product_catalog = [
        ("NB-OMEGA3", "Fish Oil Omega-3 1200 mg", 0, 0), ("NB-D3", "Vitamina D3 2000 UI", 0, 0), ("NB-MAG", "Magnesio 400 mg", 0, 0), ("NB-COLL", "Colágeno Hidrolizado", 0, 4), ("NB-B12", "Vitamina B12 Sublingual", 0, 0),
        ("CT-ADULT", "Centrum Adultos Multivitamínico", 1, 0), ("CT-WOMEN", "Centrum Mujer", 1, 0), ("CT-MEN", "Centrum Hombre", 1, 0), ("CT-SILVER", "Centrum Silver 50+", 1, 0), ("CT-ENERGY", "Centrum Energy", 1, 0),
        ("EN-ORIG", "Ensure Original Vainilla", 2, 1), ("EN-PLUS", "Ensure Plus Chocolate", 2, 1), ("EN-ADV", "Ensure Advance Fresa", 2, 1), ("EN-GLUC", "Ensure Diabetes Care", 2, 1), ("EN-HMB", "Ensure con HMB", 2, 1),
        ("VK-SYRUP", "Vicks Formula 44 Jarabe", 3, 2), ("VK-VAPO", "Vicks VapoRub Ungüento", 3, 2), ("VK-DAY", "Vicks DayQuil Cápsulas", 3, 2), ("VK-NIGHT", "Vicks NyQuil Cápsulas", 3, 2), ("VK-PAST", "Vicks Pastillas Miel", 3, 2),
        ("BY-ASP", "Aspirina Protect 100 mg", 4, 4), ("BY-RED", "Redoxon Triple Acción", 4, 0), ("BY-BEP", "Bepanthen Crema Reparadora", 4, 3), ("BY-ALKA", "Alka-Seltzer Original", 4, 4), ("BY-SUPRA", "Supradyn Activo", 4, 0),
        ("LR-EFF", "Effaclar Gel Purificante", 5, 3), ("LR-ANT", "Anthelios Fluido Invisible FPS 50+", 5, 3), ("LR-HYAL", "Hyalu B5 Sérum", 5, 3), ("LR-LIPI", "Lipikar Baume AP+M", 5, 3), ("LR-TOL", "Toleriane Dermallergo Crema", 5, 3),
        ("PS-VAIN", "PediaSure Vainilla", 6, 1), ("PS-CHOC", "PediaSure Chocolate", 6, 1), ("PS-FIBRA", "PediaSure con Fibra", 6, 1), ("PS-READY", "PediaSure Listo para Tomar", 6, 1), ("PS-POLVO", "PediaSure Polvo Nutricional", 6, 1),
        ("GNC-WHEY", "GNC Pro Performance Whey", 7, 1), ("GNC-CREA", "GNC Creatina Monohidratada", 7, 4), ("GNC-MULTI", "GNC Mega Men Multivitamínico", 7, 0), ("GNC-FISH", "GNC Triple Strength Fish Oil", 7, 0), ("GNC-GLUC", "GNC Glucosamina y Condroitina", 7, 4),
        ("KS-D3", "Kirkland Vitamina D3", 8, 0), ("KS-OMEGA", "Kirkland Fish Oil", 8, 0), ("KS-CAL", "Kirkland Calcio Citrato", 8, 4), ("KS-MEL", "Kirkland Melatonina", 8, 4), ("KS-DAILY", "Kirkland Daily Multi", 8, 0),
    ]
    base_prices = [Decimal("44.90"), Decimal("59.90"), Decimal("74.90"), Decimal("89.90"), Decimal("109.90")]
    category_adjustments = [Decimal("0"), Decimal("35"), Decimal("-15"), Decimal("20"), Decimal("10")]
    products = [
        Product(
            code=code, name=name, brand_id=brands[brand].id, category_id=categories[category].id,
            unit_price=base_prices[index % len(base_prices)] + category_adjustments[category], is_active=True,
        )
        for index, (code, name, brand, category) in enumerate(product_catalog)
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

    follow_up = ContactTypification(code="CONTACTO_EFECTIVO", name="Contacto efectivo", is_active=True)
    follow_up_child = ContactTypification(
        parent_id=None, code="SOLICITA_LLAMADA", name="Solicita llamada de seguimiento",
        is_active=True, requires_next_action=True,
    )
    no_contact = ContactTypification(code="SIN_CONTACTO", name="Sin contacto", is_active=True)
    no_response_child = ContactTypification(
        parent_id=None, code="SIN_RESPUESTA", name="Sin respuesta",
        is_active=True, requires_next_action=True,
    )
    close = ContactTypification(code="CIERRE_COMERCIAL", name="Cierre comercial", is_active=True)
    close_child = ContactTypification(
        parent_id=None, code="NO_INTERESADO", name="No interesado",
        is_active=True, requires_close=True, requires_note=True,
    )
    repurchase = ContactTypification(code="PEDIDO", name="Pedido", is_active=True)
    repurchase_child = ContactTypification(
        parent_id=None, code="PEDIDO_CONFIRMADO", name="Pedido de recompra confirmado", is_active=True,
    )
    roots = [follow_up, no_contact, close, repurchase]
    db.add_all(roots)
    db.flush()
    follow_up_child.parent_id = follow_up.id
    no_response_child.parent_id = no_contact.id
    close_child.parent_id = close.id
    repurchase_child.parent_id = repurchase.id
    db.add_all([follow_up_child, no_response_child, close_child, repurchase_child])
    db.add(AlertOperationalSettings(id=1, advisor_visibility_days=30, maximum_attempts=3, stale_days=7))

    first_names = ["María Elena", "José Luis", "Rosa María", "Carlos Alberto", "Ana Sofía", "Miguel Ángel", "Patricia", "Jorge", "Lucía", "Fernando", "Carmen", "Ricardo", "Elena", "Diego", "Valeria"]
    last_names = ["Quispe Huamán", "García Torres", "Flores Rojas", "Sánchez Medina", "Mendoza Vargas", "Castillo Paredes", "Ramírez Salazar", "Chávez López", "Vega Fernández", "Ramos Díaz", "Herrera Cruz", "Navarro Silva", "Paredes León", "Cárdenas Ruiz", "Morales Castro"]
    locations = [("LIMA", "LIMA", "MIRAFLORES", "150122"), ("LIMA", "LIMA", "SAN MIGUEL", "150136"), ("LIMA", "LIMA", "SURCO", "150143"), ("AREQUIPA", "AREQUIPA", "YANAHUARA", "040130"), ("LA LIBERTAD", "TRUJILLO", "TRUJILLO", "130101")]
    conditions = ["Hipertensión controlada", "Diabetes tipo 2", "Dolor articular", "Sin condición reportada", "Colesterol elevado"]
    customers: list[Customer] = []
    for number in range(1, 226):
        advisor = advisors[(number - 1) % len(advisors)]
        department, province, district, ubigeo = locations[(number - 1) % len(locations)]
        customers.append(Customer(
            dni=f"{70000000 + number}", first_names=first_names[(number - 1) % len(first_names)], last_names=last_names[((number - 1) // len(first_names)) % len(last_names)],
            phone=f"9{80000000 + number}", email=f"cliente.{number:03d}@ejemplo.com", status="ACTIVO",
            responsible_advisor_id=advisor.id, acquisition_channel=("DIGITAL", "TV", "OTROS")[number % 3], acquisition_channel_detail="Campaña de fidelización",
            condition=conditions[(number - 1) % len(conditions)], birth_date=date(1965 + (number % 35), (number % 12) + 1, (number % 27) + 1),
            department=department, province=province, district=district, ubigeo=ubigeo,
        ))
    db.add_all(customers)
    db.flush()
    db.add_all([
        CustomerAssignmentHistory(
            customer_id=customer.id, previous_advisor_id=None, assigned_advisor_id=customer.responsible_advisor_id,
            reason="Asignación inicial de cartera", assigned_by_user_id=actor.id, created_at=now,
        )
        for customer in customers
    ])

    original_sales: list[Sale] = []
    # A commercial catalog is not sold uniformly: these recurring products make
    # dashboard rankings meaningful while the remaining catalog stays represented.
    product_pattern = ([14] * 8 + [34] * 7 + [27] * 6 + [13] * 5 + [39] * 4
                       + [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 16])
    # These dates deliberately produce current work, recovery, follow-up, and historical cases.
    sale_dates = ([today - timedelta(days=RULE_DURATION_DAYS)] * GROUP_SIZE
                  + [today - timedelta(days=RULE_DURATION_DAYS + 40)] * GROUP_SIZE
                  + [today - timedelta(days=RULE_DURATION_DAYS + 5)] * GROUP_SIZE
                  + [today - timedelta(days=RULE_DURATION_DAYS + 10)] * GROUP_SIZE
                  + [today - timedelta(days=RULE_DURATION_DAYS + 2)] * GROUP_SIZE)
    for number, (customer, sale_date) in enumerate(zip(customers, sale_dates), start=1):
        original_sales.append(Sale(
            customer_id=customer.id, advisor_id=customer.responsible_advisor_id, sale_date=sale_date,
            notes="Compra inicial registrada durante campaña de fidelización", status="CONFIRMADA", acquisition_channel=("DIGITAL", "TV", "OTROS")[number % 3],
            acquisition_channel_detail="Campaña de fidelización",
        ))
    db.add_all(original_sales)
    db.flush()
    original_items = [
        SaleItem(
            sale_id=sale.id, product_id=products[product_pattern[(number - 1) % len(product_pattern)]].id, quantity=1,
            unit_price=products[product_pattern[(number - 1) % len(product_pattern)]].unit_price,
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
            values.update(status="REPROGRAMADO", attempts_count=1, last_contact_at=now - timedelta(days=1), next_action_date=today)
        elif group == 3:
            offset = (number - 1) % GROUP_SIZE
            if offset < REASSIGNED_ALERTS:
                values.update(status="REASIGNADO")
            elif offset < REASSIGNED_ALERTS + NO_RESPONSE_ALERTS:
                values.update(status="SIN_RESPUESTA", attempts_count=1, last_contact_at=now - timedelta(days=1), next_action_date=today)
            else:
                values.update(status="CERRADO_POR_TIPIFICACION", attempts_count=1, last_contact_at=now - timedelta(days=2), closed_at=now - timedelta(days=2), closure_reason="TIPIFICACION_DE_CIERRE: No interesado")
        elif group == 4:
            values.update(status="RECOMPRA_LOGRADA", attempts_count=1, last_contact_at=now - timedelta(days=1), closed_at=now - timedelta(days=1), closure_reason="RECOMPRA_CONFIRMADA")
        alerts.append(Alert(**values))
    db.add_all(alerts)
    db.flush()
    db.add_all([
        AlertAssignmentHistory(
            alert_id=alert.id, previous_advisor_id=None, assigned_advisor_id=alert.assigned_advisor_id,
            reason="Asignación inicial de alerta", assigned_by_user_id=actor.id, created_at=now,
        )
        for alert in alerts
    ])
    reassigned_alerts = alerts[3 * GROUP_SIZE:3 * GROUP_SIZE + REASSIGNED_ALERTS]
    for offset, alert in enumerate(reassigned_alerts):
        previous_advisor_id = alert.assigned_advisor_id
        alert.assigned_advisor_id = advisors[(offset + 1) % len(advisors)].id
        db.add(AlertAssignmentHistory(
            alert_id=alert.id, previous_advisor_id=previous_advisor_id, assigned_advisor_id=alert.assigned_advisor_id,
            reason="Redistribución de carga para seguimiento prioritario", assigned_by_user_id=actor.id, created_at=now - timedelta(days=1),
        ))

    attempts: list[AlertContactAttempt] = []
    for offset in range(GROUP_SIZE):
        managed_alert = alerts[2 * GROUP_SIZE + offset]
        repurchase_alert = alerts[4 * GROUP_SIZE + offset]
        attempts.extend([
            AlertContactAttempt(alert_id=managed_alert.id, advisor_id=managed_alert.assigned_advisor_id,
                                contacted_at=now - timedelta(days=1), channel="WHATSAPP", result=follow_up_child.code,
                                 typification_id=follow_up_child.id, note="Cliente solicita una llamada para revisar opciones de recompra.",
                                next_action_date=managed_alert.next_action_date),
            AlertContactAttempt(alert_id=repurchase_alert.id, advisor_id=repurchase_alert.assigned_advisor_id,
                                contacted_at=now - timedelta(days=1), channel="LLAMADA", result=repurchase_child.code,
                                 typification_id=repurchase_child.id, note="Cliente confirma el pedido de recompra registrado."),
        ])
    for offset in range(NO_RESPONSE_ALERTS):
        no_response_alert = alerts[3 * GROUP_SIZE + REASSIGNED_ALERTS + offset]
        attempts.append(AlertContactAttempt(
            alert_id=no_response_alert.id, advisor_id=no_response_alert.assigned_advisor_id,
            contacted_at=now - timedelta(days=1), channel="WHATSAPP", result="SIN_RESPUESTA",
            typification_id=no_response_child.id, note="No se obtuvo respuesta luego del contacto por WhatsApp.", next_action_date=today,
        ))
    for offset in range(REASSIGNED_ALERTS + NO_RESPONSE_ALERTS, GROUP_SIZE):
        closed_alert = alerts[3 * GROUP_SIZE + offset]
        attempts.append(AlertContactAttempt(
            alert_id=closed_alert.id, advisor_id=closed_alert.assigned_advisor_id,
            contacted_at=now - timedelta(days=2), channel="LLAMADA", result=close_child.code,
            typification_id=close_child.id, note="Cliente indica que no desea continuar con la recompra por el momento.",
        ))
    db.add_all(attempts)

    repurchase_sales: list[Sale] = []
    for offset in range(GROUP_SIZE):
        original_sale = original_sales[4 * GROUP_SIZE + offset]
        repurchase_sales.append(Sale(
            customer_id=original_sale.customer_id, advisor_id=original_sale.advisor_id, sale_date=today - timedelta(days=1),
            notes="Recompra confirmada desde seguimiento comercial", status="CONFIRMADA", acquisition_channel="DIGITAL",
            acquisition_channel_detail="Seguimiento de recompra", source_alert_id=alerts[4 * GROUP_SIZE + offset].id,
        ))
    db.add_all(repurchase_sales)
    db.flush()
    db.add_all([
        SaleItem(
            sale_id=sale.id, product_id=original_items[4 * GROUP_SIZE + offset].product_id, quantity=1,
            unit_price=original_items[4 * GROUP_SIZE + offset].unit_price,
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
