from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.dependencies import get_current_user, require_roles
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.products.models import Product, ProductRepurchaseRule
from app.modules.sales.models import Sale, SaleDuplicateReview, SaleItem
from app.modules.sales.schemas import AdvisorSalesMetricsResponse, AnnulSaleCreate, DuplicateReviewCreate, SaleCreate, SaleResponse
from app.modules.alerts.service import close_alerts_for_annulment, close_alerts_for_repurchase
from app.modules.alerts.models import Alert

router = APIRouter(prefix="/api/v1/sales", tags=["sales"])


def sale_response(sale: Sale, db: Session) -> dict:
    data = {column.name: getattr(sale, column.name) for column in Sale.__table__.columns}
    data["items"] = list(db.scalars(select(SaleItem).where(SaleItem.sale_id == sale.id).order_by(SaleItem.created_at)))
    return data


def get_sale_or_404(sale_id: str, db: Session) -> Sale:
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale


def assert_sale_access(sale: Sale, user: User) -> None:
    if user.role == "ASESOR" and sale.advisor_id != user.id:
        raise HTTPException(status_code=403, detail="You can only access your own sales")


def confirmed_sale_exists(customer_id: str, db: Session) -> bool:
    return db.scalar(select(Sale.id).where(Sale.customer_id == customer_id, Sale.status == "CONFIRMADA").limit(1)) is not None


def recompute_chain(customer_id: str, product_ids: set[str], db: Session) -> None:
    # Include the just-confirmed/annulled sale before deriving its neighbors.
    db.flush()
    for product_id in product_ids:
        items = list(db.scalars(
            select(SaleItem)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.customer_id == customer_id, Sale.status == "CONFIRMADA", SaleItem.product_id == product_id)
            .order_by(Sale.sale_date, Sale.created_at, SaleItem.created_at)
        ))
        previous: SaleItem | None = None
        for item in items:
            item.purchase_type = "COMPRA" if previous is None else "RECOMPRA"
            item.prior_confirmed_item_id = previous.id if previous else None
            previous = item


def rule_for(product_id: str, sale_date: date, db: Session) -> ProductRepurchaseRule | None:
    return db.scalar(
        select(ProductRepurchaseRule)
        .where(ProductRepurchaseRule.product_id == product_id, ProductRepurchaseRule.effective_from <= sale_date)
        .order_by(ProductRepurchaseRule.effective_from.desc())
        .limit(1)
    )


@router.post("", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def create_sale(payload: SaleCreate, current_user: User = Depends(require_roles("ASESOR", "SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> dict:
    # Serializing a customer's sale writes ensures a concurrent duplicate sees the first commit.
    customer = db.scalar(select(Customer).where(Customer.id == payload.customer_id).with_for_update())
    if customer is None or customer.status != "ACTIVO":
        raise HTTPException(status_code=422, detail="Customer must exist and be active")
    if current_user.role == "ASESOR" and customer.responsible_advisor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Customer is outside your portfolio")
    if payload.replaces_sale_id:
        if current_user.role not in {"SUPERVISOR", "ADMIN"}:
            raise HTTPException(status_code=403, detail="Only supervisors and administrators can register replacement sales")
        replaced_sale = get_sale_or_404(payload.replaces_sale_id, db)
        if replaced_sale.status != "ANULADA" or replaced_sale.customer_id != customer.id:
            raise HTTPException(status_code=422, detail="Replacement sale must reference an annulled sale for the same customer")
        if db.scalar(select(Sale.id).where(Sale.replaces_sale_id == replaced_sale.id).limit(1)):
            raise HTTPException(status_code=409, detail="The annulled sale already has a replacement")
    first_confirmed_sale = not confirmed_sale_exists(customer.id, db)
    if customer.acquisition_channel is None and payload.acquisition_channel is None:
        raise HTTPException(status_code=422, detail="Acquisition channel is required for the first confirmed sale")

    products = {item.product_id: db.get(Product, item.product_id) for item in payload.items}
    if any(product is None or not product.is_active for product in products.values()):
        raise HTTPException(status_code=422, detail="All products must exist and be active")
    rules = {product_id: rule_for(product_id, payload.sale_date, db) for product_id in products}
    if any(rule is None for rule in rules.values()):
        raise HTTPException(status_code=422, detail="Each product needs an effective repurchase rule on the sale date")

    duplicate = db.scalar(
        select(SaleItem.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(
            Sale.customer_id == customer.id,
            Sale.sale_date == payload.sale_date,
            Sale.status.in_(["CONFIRMADA", "PENDIENTE_REVISION_DUPLICADO"]),
            SaleItem.product_id.in_(products),
        ).limit(1)
    ) is not None
    sale = Sale(
        customer_id=customer.id, advisor_id=current_user.id, sale_date=payload.sale_date,
        notes=payload.notes.strip() if payload.notes else None,
        status="PENDIENTE_REVISION_DUPLICADO" if duplicate else "CONFIRMADA",
        acquisition_channel=payload.acquisition_channel,
        acquisition_channel_detail=payload.acquisition_channel_detail.strip() if payload.acquisition_channel_detail else None,
        replaces_sale_id=payload.replaces_sale_id,
        source_alert_id=payload.source_alert_id,
    )
    db.add(sale)
    db.flush()
    for payload_item in payload.items:
        rule = rules[payload_item.product_id]
        db.add(SaleItem(
            sale_id=sale.id, product_id=payload_item.product_id, quantity=payload_item.quantity,
            rule_duration_days=rule.duration_days, rule_alert_days=rule.alert_days,
            expected_repurchase_date=payload.sale_date + timedelta(days=rule.duration_days),
        ))
    db.flush()
    if payload.source_alert_id:
        source_alert = db.get(Alert, payload.source_alert_id)
        source_product_id = db.scalar(select(SaleItem.product_id).where(SaleItem.id == source_alert.sale_item_id)) if source_alert else None
        source_customer_id = db.scalar(select(Sale.customer_id).join(SaleItem, SaleItem.sale_id == Sale.id).where(SaleItem.id == source_alert.sale_item_id)) if source_alert else None
        if source_alert is None or source_alert.status in {"RECOMPRA_LOGRADA", "NO_INTERESADO", "CANCELADO_POR_RECOMPRA", "CANCELADO_POR_ANULACION", "VENCIDO_NO_GESTIONADO"} or source_customer_id != customer.id or source_product_id not in products:
            raise HTTPException(status_code=422, detail="Source alert must be active and belong to the customer and a sold product")
    if sale.status == "CONFIRMADA":
        if first_confirmed_sale and customer.acquisition_channel is None:
            customer.acquisition_channel = sale.acquisition_channel
            customer.acquisition_channel_detail = sale.acquisition_channel_detail
        recompute_chain(customer.id, set(products), db)
        close_alerts_for_repurchase(customer.id, set(products), sale.id, db, current_user.id, sale.source_alert_id)
    record_audit(db, actor_id=current_user.id, entity_type="sale", entity_id=sale.id, action="REPLACEMENT_CONFIRMED" if payload.replaces_sale_id else ("CONFIRMED" if sale.status == "CONFIRMADA" else "DUPLICATE_DETECTED"), after={"status": sale.status, "customer_id": customer.id, "replaces_sale_id": payload.replaces_sale_id})
    db.commit()
    return sale_response(sale, db)


@router.get("", response_model=list[SaleResponse])
def list_sales(
    customer_id: str | None = None, sale_date: date | None = None, sale_status: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(require_roles("ASESOR", "SUPERVISOR", "ADMIN")), db: Session = Depends(get_db),
) -> list[dict]:
    query = select(Sale).order_by(Sale.sale_date.desc(), Sale.created_at.desc())
    if current_user.role == "ASESOR":
        query = query.where(Sale.advisor_id == current_user.id)
    if customer_id:
        query = query.where(Sale.customer_id == customer_id)
    if sale_date:
        query = query.where(Sale.sale_date == sale_date)
    if sale_status:
        query = query.where(Sale.status == sale_status)
    return [sale_response(sale, db) for sale in db.scalars(query)]


@router.get("/me/metrics", response_model=AdvisorSalesMetricsResponse)
def advisor_sales_metrics(
    date_from: date | None = None, date_to: date | None = None,
    current_user: User = Depends(require_roles("ASESOR")), db: Session = Depends(get_db),
) -> dict[str, int]:
    query = (
        select(
            func.count(func.distinct(Sale.id)),
            func.coalesce(func.sum(SaleItem.quantity), 0),
            func.count(func.distinct(case((SaleItem.purchase_type == "RECOMPRA", Sale.id)))),
            func.coalesce(func.sum(case((SaleItem.purchase_type == "RECOMPRA", SaleItem.quantity), else_=0)), 0),
        )
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .where(Sale.advisor_id == current_user.id, Sale.status == "CONFIRMADA")
    )
    if date_from:
        query = query.where(Sale.sale_date >= date_from)
    if date_to:
        query = query.where(Sale.sale_date <= date_to)
    confirmed_sales, confirmed_items, repurchase_sales, repurchase_items = db.execute(query).one()
    return {
        "confirmed_sales": confirmed_sales,
        "confirmed_items": confirmed_items,
        "repurchase_sales": repurchase_sales,
        "repurchase_items": repurchase_items,
    }


@router.get("/{sale_id}", response_model=SaleResponse)
def get_sale(sale_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    sale = get_sale_or_404(sale_id, db)
    assert_sale_access(sale, current_user)
    return sale_response(sale, db)


@router.post("/{sale_id}/duplicate-review", response_model=SaleResponse)
def review_duplicate(
    sale_id: str, payload: DuplicateReviewCreate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)
) -> dict:
    sale = get_sale_or_404(sale_id, db)
    if sale.status != "PENDIENTE_REVISION_DUPLICADO":
        raise HTTPException(status_code=409, detail="Sale is not pending duplicate review")
    is_first_confirmed_sale = not confirmed_sale_exists(sale.customer_id, db)
    review = SaleDuplicateReview(sale_id=sale.id, decision=payload.decision, reason=payload.reason.strip(), reviewed_by_user_id=current_user.id)
    db.add(review)
    sale.status = "CONFIRMADA" if payload.decision == "APROBADA" else "RECHAZADA_DUPLICADO"
    if sale.status == "RECHAZADA_DUPLICADO":
        # A rejected duplicate must not reserve an otherwise active source alert.
        sale.source_alert_id = None
    if sale.status == "CONFIRMADA":
        customer = db.get(Customer, sale.customer_id)
        if is_first_confirmed_sale and customer.acquisition_channel is None:
            if sale.acquisition_channel is None:
                raise HTTPException(status_code=422, detail="Acquisition channel is required for the first confirmed sale")
            customer.acquisition_channel = sale.acquisition_channel
            customer.acquisition_channel_detail = sale.acquisition_channel_detail
        product_ids = set(db.scalars(select(SaleItem.product_id).where(SaleItem.sale_id == sale.id)))
        recompute_chain(sale.customer_id, product_ids, db)
        close_alerts_for_repurchase(sale.customer_id, product_ids, sale.id, db, current_user.id, sale.source_alert_id)
    record_audit(db, actor_id=current_user.id, entity_type="sale", entity_id=sale.id, action="DUPLICATE_" + payload.decision, before={"status": "PENDIENTE_REVISION_DUPLICADO"}, after={"status": sale.status, "reason": review.reason})
    db.commit()
    return sale_response(sale, db)


@router.post("/{sale_id}/annul", response_model=SaleResponse)
def annul_sale(
    sale_id: str, payload: AnnulSaleCreate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)
) -> dict:
    sale = get_sale_or_404(sale_id, db)
    if sale.status != "CONFIRMADA":
        raise HTTPException(status_code=409, detail="Only confirmed sales can be annulled")
    product_ids = set(db.scalars(select(SaleItem.product_id).where(SaleItem.sale_id == sale.id)))
    sale.status = "ANULADA"
    sale.annulled_by_user_id = current_user.id
    sale.annulment_reason = payload.reason.strip()
    sale.annulled_at = datetime.now(timezone.utc)
    close_alerts_for_annulment(sale.id, db, current_user.id)
    recompute_chain(sale.customer_id, product_ids, db)
    record_audit(db, actor_id=current_user.id, entity_type="sale", entity_id=sale.id, action="ANNULLED", before={"status": "CONFIRMADA"}, after={"status": "ANULADA", "reason": sale.annulment_reason})
    db.commit()
    return sale_response(sale, db)
