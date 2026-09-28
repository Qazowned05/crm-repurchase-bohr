from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.pagination import paginate_items
from app.dependencies import get_current_user, require_roles
from app.modules.auth.models import User
from app.modules.products.models import Brand, Product, ProductCategory, ProductRepurchaseRule
from app.modules.products.schemas import CatalogCreate, CatalogResponse, CatalogUpdate, ProductCreate, ProductResponse, ProductUpdate, RuleCreate, RuleResponse

router = APIRouter(prefix="/api/v1/products", tags=["products"])
brands_router = APIRouter(prefix="/api/v1/brands", tags=["brands"])
categories_router = APIRouter(prefix="/api/v1/product-categories", tags=["product-categories"])


def get_product_or_404(product_id: str, db: Session) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def active_catalog_record(model: type[Brand] | type[ProductCategory], record_id: str, label: str, db: Session) -> Brand | ProductCategory:
    record = db.get(model, record_id)
    if record is None or not record.is_active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Active {label} not found")
    return record


def product_response(product: Product) -> dict:
    return {"id": product.id, "code": product.code, "name": product.name, "brand_id": product.brand_id,
            "category_id": product.category_id, "brand_name": product.brand.name,
            "category_name": product.category.name, "is_active": product.is_active,
            "created_at": product.created_at, "updated_at": product.updated_at}


@router.get("", response_model=None)
def list_products(
    include_inactive: bool = False,
    page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict] | dict:
    query = select(Product).options(selectinload(Product.brand), selectinload(Product.category)).order_by(Product.name)
    if not include_inactive:
        query = query.where(Product.is_active.is_(True))
    return paginate_items([product_response(product) for product in db.scalars(query)], page, page_size)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")),
    db: Session = Depends(get_db),
) -> dict:
    if db.scalar(select(Product).where(Product.code == payload.code)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product code already exists")
    active_catalog_record(Brand, payload.brand_id, "brand", db)
    active_catalog_record(ProductCategory, payload.category_id, "product category", db)
    product = Product(code=payload.code, name=payload.name.strip(), brand_id=payload.brand_id, category_id=payload.category_id)
    db.add(product)
    db.flush()
    record_audit(
        db,
        actor_id=current_user.id,
        entity_type="product",
        entity_id=product.id,
        action="CREATED",
        after={"code": product.code, "name": product.name, "brand_id": product.brand_id, "category_id": product.category_id},
    )
    db.commit()
    db.refresh(product)
    return product_response(product)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    payload: ProductUpdate,
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")),
    db: Session = Depends(get_db),
) -> dict:
    product = get_product_or_404(product_id, db)
    changes = payload.model_dump(exclude_unset=True)
    if "brand_id" in changes:
        active_catalog_record(Brand, changes["brand_id"], "brand", db)
    if "category_id" in changes:
        active_catalog_record(ProductCategory, changes["category_id"], "product category", db)
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
    return product_response(product)


@router.get("/{product_id}/rules", response_model=None)
def list_rules(
    product_id: str, page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200), _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ProductRepurchaseRule] | dict:
    get_product_or_404(product_id, db)
    rows = list(
        db.scalars(
            select(ProductRepurchaseRule)
            .where(ProductRepurchaseRule.product_id == product_id)
            .order_by(ProductRepurchaseRule.effective_from.desc())
        )
    )
    return paginate_items(rows, page, page_size)


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


def catalog_routes(router: APIRouter, model: type[Brand] | type[ProductCategory], label: str) -> None:
    @router.get("", response_model=None)
    def list_records(include_inactive: bool = False, page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200), _: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> list[Brand | ProductCategory] | dict:
        query = select(model).order_by(model.name)
        if not include_inactive:
            query = query.where(model.is_active.is_(True))
        return paginate_items(list(db.scalars(query)), page, page_size)

    @router.post("", response_model=CatalogResponse, status_code=status.HTTP_201_CREATED)
    def create_record(payload: CatalogCreate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> Brand | ProductCategory:
        record = model(**payload.model_dump())
        db.add(record)
        try:
            db.flush()
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{label} name already exists") from error
        record_audit(db, actor_id=current_user.id, entity_type=label.replace(" ", "_"), entity_id=record.id, action="CREATED", after=payload.model_dump())
        db.commit(); db.refresh(record)
        return record

    @router.patch("/{record_id}", response_model=CatalogResponse)
    def update_record(record_id: str, payload: CatalogUpdate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> Brand | ProductCategory:
        record = db.get(model, record_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label.title()} not found")
        changes = payload.model_dump(exclude_unset=True)
        before = {field: getattr(record, field) for field in changes}
        for field, value in changes.items():
            setattr(record, field, value)
        try:
            db.flush()
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{label} name already exists") from error
        record_audit(db, actor_id=current_user.id, entity_type=label.replace(" ", "_"), entity_id=record.id, action="UPDATED", before=before, after=changes)
        db.commit(); db.refresh(record)
        return record

    @router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_record(record_id: str, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> None:
        record = db.get(model, record_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label.title()} not found")
        column = Product.brand_id if model is Brand else Product.category_id
        if db.scalar(select(Product.id).where(column == record.id).limit(1)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{label.title()} cannot be deleted while referenced by products")
        record_audit(db, actor_id=current_user.id, entity_type=label.replace(" ", "_"), entity_id=record.id, action="DELETED", before={"name": record.name})
        db.delete(record); db.commit()


catalog_routes(brands_router, Brand, "brand")
catalog_routes(categories_router, ProductCategory, "product category")
