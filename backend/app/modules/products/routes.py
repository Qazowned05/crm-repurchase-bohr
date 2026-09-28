from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.dependencies import get_current_user, require_roles
from app.modules.auth.models import User
from app.modules.products.models import Product, ProductRepurchaseRule
from app.modules.products.schemas import ProductCreate, ProductResponse, ProductUpdate, RuleCreate, RuleResponse

router = APIRouter(prefix="/api/v1/products", tags=["products"])


def get_product_or_404(product_id: str, db: Session) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.get("", response_model=list[ProductResponse])
def list_products(
    include_inactive: bool = False,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Product]:
    query = select(Product).order_by(Product.name)
    if not include_inactive:
        query = query.where(Product.is_active.is_(True))
    return list(db.scalars(query))


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")),
    db: Session = Depends(get_db),
) -> Product:
    if db.scalar(select(Product).where(Product.code == payload.code)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product code already exists")
    product = Product(code=payload.code, name=payload.name.strip(), category=payload.category.strip())
    db.add(product)
    db.flush()
    record_audit(
        db,
        actor_id=current_user.id,
        entity_type="product",
        entity_id=product.id,
        action="CREATED",
        after={"code": product.code, "name": product.name, "category": product.category},
    )
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    payload: ProductUpdate,
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")),
    db: Session = Depends(get_db),
) -> Product:
    product = get_product_or_404(product_id, db)
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(product, field) for field in changes}
    for field, value in changes.items():
        setattr(product, field, value)
    record_audit(
        db,
        actor_id=current_user.id,
        entity_type="product",
        entity_id=product.id,
        action="UPDATED",
        before=before,
        after={field: getattr(product, field) for field in changes},
    )
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}/rules", response_model=list[RuleResponse])
def list_rules(
    product_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ProductRepurchaseRule]:
    get_product_or_404(product_id, db)
    return list(
        db.scalars(
            select(ProductRepurchaseRule)
            .where(ProductRepurchaseRule.product_id == product_id)
            .order_by(ProductRepurchaseRule.effective_from.desc())
        )
    )


@router.post("/{product_id}/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(
    product_id: str,
    payload: RuleCreate,
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")),
    db: Session = Depends(get_db),
) -> ProductRepurchaseRule:
    get_product_or_404(product_id, db)
    try:
        payload.validate_for_duration()
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    existing = db.scalar(
        select(ProductRepurchaseRule).where(
            ProductRepurchaseRule.product_id == product_id,
            ProductRepurchaseRule.effective_from == payload.effective_from,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A rule already exists for this effective date")
    rule = ProductRepurchaseRule(
        product_id=product_id,
        duration_days=payload.duration_days,
        alert_days=payload.alert_days,
        effective_from=payload.effective_from,
        medical_approval_reference=payload.medical_approval_reference,
        medical_approved_by=payload.medical_approved_by,
        medical_approved_at=payload.medical_approved_at,
        created_by_user_id=current_user.id,
    )
    db.add(rule)
    db.flush()
    record_audit(
        db,
        actor_id=current_user.id,
        entity_type="product_rule",
        entity_id=rule.id,
        action="CREATED",
        after={"product_id": product_id, "duration_days": rule.duration_days, "effective_from": str(rule.effective_from)},
    )
    db.commit()
    db.refresh(rule)
    return rule
