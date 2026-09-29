"""Seed a small local dataset for alert and reassignment testing."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.alerts.models import Alert
from app.modules.auth.models import User
from app.modules.configuration.models import AlertOperationalSettings
from app.modules.customers.models import Customer
from app.modules.products.models import Brand, Product, ProductCategory, ProductRepurchaseRule
from app.modules.sales.models import Sale, SaleItem
from app.modules.supervision.models import AlertAssignmentHistory


def main() -> None:
    with SessionLocal() as db:
        if db.scalar(select(Product.id).where(Product.code == "DEMO-LOCAL-01")):
            print("Small local demo dataset already exists.")
            return

        today = date.today()
        now = datetime.now(timezone.utc)
        advisors = [
            User(email="ana.demo@example.com", full_name="Ana Demo", password_hash=hash_password("Demo2026!"), role="ASESOR"),
            User(email="luis.demo@example.com", full_name="Luis Demo", password_hash=hash_password("Demo2026!"), role="ASESOR"),
        ]
        brand = Brand(name="Demo Local")
        category = ProductCategory(name="Pruebas de alertas")
        db.add_all(advisors + [brand, category])
        db.flush()

        products = [
            Product(code="DEMO-LOCAL-01", name="Plan de mantenimiento", brand_id=brand.id, category_id=category.id),
            Product(code="DEMO-LOCAL-02", name="Kit de repuesto", brand_id=brand.id, category_id=category.id),
        ]
        db.add_all(products)
        db.flush()
        db.add_all([
            ProductRepurchaseRule(product_id=product.id, duration_days=60, alert_days=[14, 7], effective_from=today - timedelta(days=365), created_by_user_id=advisors[0].id)
            for product in products
        ])
        if db.get(AlertOperationalSettings, 1) is None:
            db.add(AlertOperationalSettings(id=1, advisor_visibility_days=30, maximum_attempts=3, stale_days=7))

        customers = [
            Customer(dni=f"DEMO-LOCAL-0{number}", first_names=first_name, last_names="Prueba", phone=f"+5199900000{number}", email=f"{first_name.lower()}.prueba@example.test", responsible_advisor_id=advisors[(number - 1) % 2].id)
            for number, first_name in enumerate(["Alba", "Bruno", "Carla", "Diego"], start=1)
        ]
        db.add_all(customers)
        db.flush()

        alert_specs = [
            (60, "PENDIENTE", 0, None),
            (105, "VENCIDO_NO_GESTIONADO", 0, None),
            (65, "PENDIENTE", 1, now - timedelta(days=10)),
            (70, "REPROGRAMADO", 3, now - timedelta(days=2)),
        ]
        alerts = []
        for number, (sale_age, status, attempts, last_contact) in enumerate(alert_specs):
            sale_date = today - timedelta(days=sale_age)
            sale = Sale(customer_id=customers[number].id, advisor_id=customers[number].responsible_advisor_id, sale_date=sale_date, notes="Venta historica de demostracion", status="CONFIRMADA")
            db.add(sale)
            db.flush()
            item = SaleItem(sale_id=sale.id, product_id=products[number % len(products)].id, quantity=1, unit_price=100, rule_duration_days=60, rule_alert_days=[14, 7], expected_repurchase_date=sale_date + timedelta(days=60), purchase_type="COMPRA")
            db.add(item)
            db.flush()
            alert = Alert(sale_item_id=item.id, assigned_advisor_id=sale.advisor_id, alert_date=item.expected_repurchase_date, expected_repurchase_date=item.expected_repurchase_date, status=status, attempts_count=attempts, last_contact_at=last_contact, closed_at=now if status == "VENCIDO_NO_GESTIONADO" else None)
            db.add(alert)
            alerts.append(alert)
        db.flush()
        db.add_all([
            AlertAssignmentHistory(alert_id=alert.id, previous_advisor_id=None, assigned_advisor_id=alert.assigned_advisor_id, reason="Asignacion inicial demo local", assigned_by_user_id=advisors[0].id)
            for alert in alerts
        ])
        db.commit()
        print("Seeded 4 customers, 4 historical sales, and 4 recoverable alert scenarios.")


if __name__ == "__main__":
    main()
