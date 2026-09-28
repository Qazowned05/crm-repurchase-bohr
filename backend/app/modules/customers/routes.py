from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.pagination import paginate_items
from app.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.customers.schemas import CustomerCreate, CustomerResponse, CustomerSupervisorUpdate
from app.modules.sales.models import Sale, SaleItem
from app.modules.sales.schemas import SaleResponse
from app.modules.sales.routes import sale_response

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


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
        birth_year=payload.birth_year,
        sales_district=payload.sales_district.strip() if payload.sales_district else None,
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
    changes = payload.model_dump(exclude_unset=True)
    protected = {"responsible_advisor_id", "status"}
    if current_user.role == "ASESOR" and protected.intersection(changes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only supervisors can change status or assignment")
    if "responsible_advisor_id" in changes:
        validate_responsible(changes["responsible_advisor_id"], db)
    before = {field: getattr(customer, field) for field in changes}
    for field, value in changes.items():
        if field == "email" and value is not None:
            value = str(value).lower()
        if field in {"condition", "sales_district"} and value is not None:
            value = value.strip() or None
        setattr(customer, field, value)
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
