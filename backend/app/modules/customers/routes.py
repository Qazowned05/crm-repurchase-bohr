from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.pagination import paginate_items
from app.dependencies import get_current_user
from app.modules.alerts.models import Alert
from app.modules.alerts.service import active_alerts_query
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.customers.schemas import CustomerCreate, CustomerResponse, CustomerSupervisorUpdate
from app.data.ubigeo import location_by_ubigeo, location_hierarchy
from app.modules.sales.models import Sale, SaleItem
from app.modules.sales.schemas import SaleResponse
from app.modules.sales.routes import sale_response
from app.modules.supervision.models import AlertAssignmentHistory, CustomerAssignmentHistory

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


def validate_location(payload: CustomerCreate | CustomerSupervisorUpdate, customer: Customer | None = None) -> dict[str, str] | None:
    changes = payload.model_dump(exclude_unset=True)
    fields = ("department", "province", "district", "ubigeo")
    if not any(field in changes for field in fields):
        return None
    values = {field: changes.get(field, getattr(customer, field) if customer else None) for field in fields}
    if not all(values.values()):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="department, province, district, and ubigeo must be provided together")
    location = location_by_ubigeo().get(values["ubigeo"])
    if location is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The selected UBIGEO does not exist")
    for field, expected in (("department", "department_name"), ("province", "province_name"), ("district", "district_name")):
        value = values[field]
        if value != location[expected]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The selected location is inconsistent")
    return location


@router.get("/locations")
def list_locations(current_user: User = Depends(get_current_user)) -> list[dict]:
    return location_hierarchy()


def get_customer_or_404(customer_id: str, db: Session) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


def assert_customer_access(customer: Customer, current_user: User) -> None:
    if current_user.role == "ASESOR" and customer.responsible_advisor_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer is outside your portfolio")


def validate_responsible(advisor_id: str | None, db: Session) -> None:
    if advisor_id is None:
        return
    advisor = db.get(User, advisor_id)
    if advisor is None or not advisor.is_active or advisor.role != "ASESOR":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Responsible advisor must be active")


def transfer_customer_assignment(customer: Customer, advisor_id: str | None, reason: str, actor_id: str, db: Session) -> None:
    previous_advisor_id = customer.responsible_advisor_id
    if advisor_id == previous_advisor_id:
        return
    customer.responsible_advisor_id = advisor_id
    db.add(CustomerAssignmentHistory(
        customer_id=customer.id,
        previous_advisor_id=previous_advisor_id,
        assigned_advisor_id=advisor_id,
        reason=reason,
        assigned_by_user_id=actor_id,
    ))
    alerts = db.scalars(
        active_alerts_query()
        .join(SaleItem, SaleItem.id == Alert.sale_item_id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.customer_id == customer.id)
    )
    for alert in alerts:
        previous_alert_advisor_id = alert.assigned_advisor_id
        alert.assigned_advisor_id = advisor_id
        db.add(AlertAssignmentHistory(
            alert_id=alert.id,
            previous_advisor_id=previous_alert_advisor_id,
            assigned_advisor_id=advisor_id,
            reason=reason,
            assigned_by_user_id=actor_id,
        ))
        record_audit(
            db,
            actor_id=actor_id,
            entity_type="alert",
            entity_id=alert.id,
            action="ASSIGNED",
            before={"assigned_advisor_id": previous_alert_advisor_id},
            after={"assigned_advisor_id": advisor_id, "reason": reason},
        )
    record_audit(
        db,
        actor_id=actor_id,
        entity_type="customer",
        entity_id=customer.id,
        action="PORTFOLIO_TRANSFERRED",
        before={"responsible_advisor_id": previous_advisor_id},
        after={"responsible_advisor_id": advisor_id, "reason": reason},
    )


@router.get("", response_model=None)
def list_customers(
    q: str | None = Query(default=None, max_length=120),
    page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Customer] | dict:
    query = select(Customer).order_by(Customer.last_names, Customer.first_names)
    if current_user.role == "ASESOR":
        query = query.where(Customer.responsible_advisor_id == current_user.id)
    if q:
        term = f"%{q.strip()}%"
        query = query.where(or_(Customer.dni.ilike(term), Customer.first_names.ilike(term), Customer.last_names.ilike(term)))
    return paginate_items(list(db.scalars(query)), page, page_size)


@router.get("/sale-options", response_model=list[CustomerResponse])
def list_sale_options(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Customer]:
    """Sale choices are limited to the advisor's active portfolio."""
    query = select(Customer).where(Customer.status == "ACTIVO")
    if current_user.role == "ASESOR":
        query = query.where(Customer.responsible_advisor_id == current_user.id)
    return list(db.scalars(query.order_by(Customer.last_names, Customer.first_names)))


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Customer:
    customer = get_customer_or_404(customer_id, db)
    assert_customer_access(customer, current_user)
    return customer


@router.get("/{customer_id}/sales", response_model=None)
def customer_sales_history(
    customer_id: str, page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict] | dict:
    customer = get_customer_or_404(customer_id, db)
    assert_customer_access(customer, current_user)
    sales = db.scalars(select(Sale).where(Sale.customer_id == customer.id).order_by(Sale.sale_date.desc(), Sale.created_at.desc()))
    return paginate_items([sale_response(sale, db) for sale in sales], page, page_size)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Customer:
    validate_location(payload)
    if db.scalar(select(Customer).where(Customer.dni == payload.dni)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="DNI already exists")
    responsible_id = current_user.id if current_user.role == "ASESOR" else payload.responsible_advisor_id
    validate_responsible(responsible_id, db)
    customer = Customer(
        dni=payload.dni,
        first_names=payload.first_names.strip(),
        last_names=payload.last_names.strip(),
        phone=payload.phone.strip(),
        email=str(payload.email).lower() if payload.email else None,
        responsible_advisor_id=responsible_id,
        condition=payload.condition.strip() if payload.condition else None,
        birth_date=payload.birth_date,
        department=payload.department,
        province=payload.province,
        district=payload.district,
        ubigeo=payload.ubigeo,
    )
    db.add(customer)
    db.flush()
    record_audit(
        db,
        actor_id=current_user.id,
        entity_type="customer",
        entity_id=customer.id,
        action="CREATED",
        after={"dni": customer.dni, "responsible_advisor_id": customer.responsible_advisor_id},
    )
    db.commit()
    db.refresh(customer)
    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    payload: CustomerSupervisorUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Customer:
    customer = get_customer_or_404(customer_id, db)
    assert_customer_access(customer, current_user)
    validate_location(payload, customer)
    changes = payload.model_dump(exclude_unset=True)
    protected = {"responsible_advisor_id", "status"}
    if current_user.role == "ASESOR" and protected.intersection(changes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only supervisors can change status or assignment")
    advisor_id = changes.pop("responsible_advisor_id", None) if "responsible_advisor_id" in changes else None
    has_assignment_change = "responsible_advisor_id" in payload.model_fields_set
    if has_assignment_change:
        validate_responsible(advisor_id, db)
    before = {field: getattr(customer, field) for field in changes}
    for field, value in changes.items():
        if field == "email" and value is not None:
            value = str(value).lower()
        if field == "condition" and value is not None:
            value = value.strip() or None
        setattr(customer, field, value)
    if has_assignment_change:
        transfer_customer_assignment(customer, advisor_id, "Actualización de responsable desde la ficha de cliente", current_user.id, db)
    record_audit(
        db,
        actor_id=current_user.id,
        entity_type="customer",
        entity_id=customer.id,
        action="UPDATED",
        before=before,
        after={field: getattr(customer, field) for field in changes},
    )
    db.commit()
    db.refresh(customer)
    return customer
