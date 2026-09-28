from datetime import date, datetime, timezone
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import settings
from app.core.database import get_db
from app.dependencies import require_roles
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.customers.schemas import CustomerCreate
from app.modules.imports.models import ImportJob, ImportRowError
from app.modules.products.models import Brand, Product, ProductCategory, ProductRepurchaseRule
from app.modules.products.schemas import RuleCreate

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])

HEADERS = {
    "customers": ["dni", "first_names", "last_names", "phone", "email", "responsible_advisor_email"],
    "products": ["code", "name", "brand", "category", "is_active", "duration_days", "alert_days", "effective_from"],
}


def job_response(job: ImportJob, db: Session) -> dict:
    errors = list(db.scalars(select(ImportRowError).where(ImportRowError.import_job_id == job.id).order_by(ImportRowError.row_number)))
    return {"id": job.id, "type": job.import_type, "state": job.state, "total_rows": job.total_rows,
            "valid_rows": job.valid_rows, "new_rows": job.new_rows, "update_rows": job.update_rows,
            "rejected_rows": job.rejected_rows, "errors": [{"row_number": e.row_number, "field": e.field, "message": e.message} for e in errors]}


def add_error(errors: list[dict], row: int | None, message: str, field: str | None = None) -> None:
    errors.append({"row_number": row, "field": field, "message": message})


def cell_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def catalog_record(model: type[Brand] | type[ProductCategory], name: str, label: str, db: Session) -> Brand | ProductCategory:
    record = db.scalar(select(model).where(model.name == name.strip()))
    if record is None or not record.is_active:
        raise ValueError(f"{label} must be an existing active catalog entry")
    return record


def workbook_rows(content: bytes, import_type: str) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = archive.namelist()
            if any(name.lower().endswith(("vbaproject.bin", ".bin")) for name in names):
                return [], [{"row_number": None, "field": None, "message": "Macro-enabled workbooks are not allowed"}]
            if sum(info.file_size for info in archive.infolist()) > settings.import_max_file_size * 10:
                return [], [{"row_number": None, "field": None, "message": "Workbook expands beyond the allowed limit"}]
    except BadZipFile:
        return [], [{"row_number": None, "field": None, "message": "Invalid or corrupt XLSX file"}]
    try:
        workbook = load_workbook(BytesIO(content), read_only=False, data_only=False, keep_vba=False)
    except Exception:
        return [], [{"row_number": None, "field": None, "message": "Invalid or corrupt XLSX file"}]
    if workbook.security.lockStructure:
        return [], [{"row_number": None, "field": None, "message": "Protected workbooks are not allowed"}]
    if "Data" not in workbook.sheetnames:
        return [], [{"row_number": None, "field": None, "message": "Workbook must contain a Data sheet"}]
    sheet = workbook["Data"]
    if sheet.protection.sheet:
        return [], [{"row_number": None, "field": None, "message": "Protected worksheets are not allowed"}]
    headers = [cell_text(cell.value) for cell in sheet[1]]
    if headers != HEADERS[import_type]:
        return [], [{"row_number": 1, "field": None, "message": "Headers must exactly match the template"}]
    rows: list[dict] = []
    for row_number, cells in enumerate(sheet.iter_rows(min_row=2), start=2):
        if all(cell.value is None for cell in cells):
            continue
        if any(cell.data_type == "f" for cell in cells):
            add_error(errors, row_number, "Formulas are not allowed in data fields")
            continue
        if len(rows) >= settings.import_max_rows:
            add_error(errors, row_number, f"Workbook exceeds {settings.import_max_rows} data rows")
            break
        row = {header: cell_text(cell.value) for header, cell in zip(HEADERS[import_type], cells, strict=False)}
        rows.append({"row_number": row_number, "data": row})
    return rows, errors


def validate_rows(rows: list[dict], import_type: str, db: Session, allow_updates: bool, allow_reassignment: bool) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    seen: set[str] = set()
    valid: list[dict] = []
    for source in rows:
        row_number, data = source["row_number"], source["data"]
        key = data["dni"] if import_type == "customers" else data["code"]
        key = key.upper() if key else None
        if not key:
            add_error(errors, row_number, "Identifier is required", "dni" if import_type == "customers" else "code")
            continue
        if key in seen:
            add_error(errors, row_number, "Duplicate identifier within workbook", "dni" if import_type == "customers" else "code")
            continue
        seen.add(key)
        try:
            if import_type == "customers":
                data["dni"] = key
                existing = db.scalar(select(Customer).where(Customer.dni == key))
                action = "update" if existing else "new"
                if existing and not allow_updates:
                    raise ValueError("Customer already exists; enable allow_updates to update it")
                if not existing:
                    CustomerCreate(**{field: data[field] for field in ("dni", "first_names", "last_names", "phone", "email")})
                else:
                    CustomerCreate(**{
                        "dni": data["dni"],
                        "first_names": data["first_names"] or existing.first_names,
                        "last_names": data["last_names"] or existing.last_names,
                        "phone": data["phone"] or existing.phone,
                        "email": data["email"] if data["email"] is not None else existing.email,
                    })
                advisor_email = data.pop("responsible_advisor_email", None)
                if advisor_email:
                    advisor = db.scalar(select(User).where(User.email == advisor_email.lower()))
                    if advisor is None or not advisor.is_active or advisor.role != "ASESOR":
                        raise ValueError("Responsible advisor must be an active ASESOR")
                    if existing and advisor.id != existing.responsible_advisor_id and not allow_reassignment:
                        raise ValueError("Enable allow_reassignment to change the responsible advisor")
                    data["responsible_advisor_id"] = advisor.id
            else:
                data["code"] = key
                existing = db.scalar(select(Product).where(Product.code == key))
                action = "update" if existing else "new"
                if existing and not allow_updates:
                    raise ValueError("Product code already exists; enable allow_updates to update it")
                if not existing:
                    if not data["name"] or not data["brand"] or not data["category"]:
                        raise ValueError("name, brand, and category are required for new products")
                    catalog_record(Brand, data["brand"], "Brand", db)
                    catalog_record(ProductCategory, data["category"], "Category", db)
                else:
                    if data["brand"]:
                        catalog_record(Brand, data["brand"], "Brand", db)
                    if data["category"]:
                        catalog_record(ProductCategory, data["category"], "Category", db)
                data["is_active"] = parse_bool(data["is_active"]) if data["is_active"] else None
                rule_fields = ["duration_days", "alert_days", "effective_from"]
                supplied = [field for field in rule_fields if data[field] is not None]
                if supplied and len(supplied) != len(rule_fields):
                    raise ValueError("All repurchase-rule fields are required when importing a rule")
                if supplied:
                    data["duration_days"] = int(data["duration_days"])
                    data["alert_days"] = [int(day.strip()) for day in data["alert_days"].split(",")]
                    data["effective_from"] = date.fromisoformat(data["effective_from"]).isoformat()
                    RuleCreate(**{field: data[field] for field in rule_fields})
                    if existing and db.scalar(select(ProductRepurchaseRule).where(ProductRepurchaseRule.product_id == existing.id, ProductRepurchaseRule.effective_from == date.fromisoformat(data["effective_from"]))) is not None:
                        raise ValueError("A repurchase rule already exists for this effective date")
            valid.append({"row_number": row_number, "action": action, "data": data})
        except (ValidationError, ValueError, TypeError) as error:
            add_error(errors, row_number, str(error))
    return valid, errors


def parse_bool(value: str) -> bool:
    if value.lower() in {"true", "1", "yes", "si", "sí"}:
        return True
    if value.lower() in {"false", "0", "no"}:
        return False
    raise ValueError("is_active must be true or false")


@router.get("/templates/{import_type}")
def download_template(import_type: str, _: User = Depends(require_roles("SUPERVISOR", "ADMIN"))) -> StreamingResponse:
    if import_type not in HEADERS:
        raise HTTPException(status_code=404, detail="Unknown import type")
    workbook = Workbook()
    instructions = workbook.active
    instructions.title = "Instructions"
    instructions.append(["Secure import template"])
    instructions.append(["Use the Data sheet only. Do not change headers, add formulas, macros, or sheet protection."])
    instructions.append(["Blank cells do not overwrite existing values. Updates require preview with allow_updates."])
    sheet = workbook.create_sheet("Data")
    sheet.append(HEADERS[import_type])
    sheet.freeze_panes = "A2"
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    example = (["99999999", "Ana", "Ejemplo", "999999999", "ana@example.invalid", ""] if import_type == "customers" else
               ["EXAMPLE-001", "Producto de ejemplo", "SIN MARCA", "Ejemplos", "true", "30", "15,5", "2026-01-01"])
    sheet.append(example)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{import_type}_template.xlsx"'})


@router.post("/{import_type}/preview", status_code=status.HTTP_201_CREATED)
async def preview_import(import_type: str, file: UploadFile = File(...), allow_updates: bool = Form(False), allow_reassignment: bool = Form(False), current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> dict:
    if import_type not in HEADERS:
        raise HTTPException(status_code=404, detail="Unknown import type")
    filename = file.filename or "upload.xlsx"
    content = await file.read(settings.import_max_file_size + 1)
    errors: list[dict] = []
    rows: list[dict] = []
    if not filename.lower().endswith(".xlsx"):
        add_error(errors, None, "Only .xlsx files are accepted")
    elif len(content) > settings.import_max_file_size:
        add_error(errors, None, f"File exceeds {settings.import_max_file_size} byte limit")
    else:
        rows, errors = workbook_rows(content, import_type)
        if not errors:
            valid, validation_errors = validate_rows(rows, import_type, db, allow_updates, allow_reassignment)
            errors.extend(validation_errors)
        else:
            valid = []
    job = ImportJob(import_type=import_type, created_by_user_id=current_user.id, source_filename=filename, source_file=content, allow_updates=allow_updates, allow_reassignment=allow_reassignment, total_rows=len(rows), valid_rows=len(valid), new_rows=sum(row["action"] == "new" for row in valid), update_rows=sum(row["action"] == "update" for row in valid), rejected_rows=len(errors), rows_data=valid, state="PREVIEW_ERRORS" if errors else "PREVIEW_READY")
    db.add(job)
    db.flush()
    for error in errors:
        db.add(ImportRowError(import_job_id=job.id, **error))
    record_audit(db, actor_id=current_user.id, entity_type="import_job", entity_id=job.id, action="PREVIEWED", after={"type": import_type, "state": job.state, "total_rows": job.total_rows})
    db.commit()
    return job_response(job, db)


@router.get("/{job_id}")
def get_import_job(job_id: str, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> dict:
    job = db.get(ImportJob, job_id)
    if job is None or (job.created_by_user_id != current_user.id and current_user.role != "ADMIN"):
        raise HTTPException(status_code=404, detail="Import job not found")
    return job_response(job, db)


@router.get("/{job_id}/errors")
def download_errors(job_id: str, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> StreamingResponse:
    job = db.get(ImportJob, job_id)
    if job is None or (job.created_by_user_id != current_user.id and current_user.role != "ADMIN"):
        raise HTTPException(status_code=404, detail="Import job not found")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Errors"
    sheet.append(["row_number", "field", "message"])
    for error in db.scalars(select(ImportRowError).where(ImportRowError.import_job_id == job.id).order_by(ImportRowError.row_number)):
        sheet.append([error.row_number, error.field, error.message])
    output = BytesIO(); workbook.save(output); output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="import_{job.id}_errors.xlsx"'})


@router.post("/{job_id}/commit")
def commit_import(job_id: str, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> dict:
    job = db.get(ImportJob, job_id)
    if job is None or (job.created_by_user_id != current_user.id and current_user.role != "ADMIN"):
        raise HTTPException(status_code=404, detail="Import job not found")
    if job.state != "PREVIEW_READY":
        raise HTTPException(status_code=409, detail="Only a clean preview can be committed")
    try:
        for row in job.rows_data:
            data = row["data"]
            if job.import_type == "customers":
                customer = db.scalar(select(Customer).where(Customer.dni == data["dni"]))
                if customer is None:
                    customer = Customer(**{field: data[field] for field in ("dni", "first_names", "last_names", "phone", "email", "responsible_advisor_id") if data.get(field) is not None})
                    db.add(customer); db.flush()
                    record_audit(db, actor_id=current_user.id, entity_type="customer", entity_id=customer.id, action="CREATED", after={"dni": customer.dni, "import_job_id": job.id})
                elif job.allow_updates:
                    before = {}; changes = {field: data[field] for field in ("first_names", "last_names", "phone", "email", "responsible_advisor_id") if data.get(field) is not None}
                    if "email" in changes:
                        changes["email"] = changes["email"].lower()
                    for field, value in changes.items(): before[field] = getattr(customer, field); setattr(customer, field, value)
                    if changes: record_audit(db, actor_id=current_user.id, entity_type="customer", entity_id=customer.id, action="UPDATED", before=before, after=changes)
                else: raise ValueError(f"Customer {data['dni']} now conflicts with an existing record")
            else:
                product = db.scalar(select(Product).where(Product.code == data["code"]))
                if product is None:
                    brand = catalog_record(Brand, data["brand"], "Brand", db)
                    category = catalog_record(ProductCategory, data["category"], "Category", db)
                    product = Product(code=data["code"], name=data["name"].strip(), brand_id=brand.id, category_id=category.id, is_active=True if data["is_active"] is None else data["is_active"])
                    db.add(product); db.flush(); record_audit(db, actor_id=current_user.id, entity_type="product", entity_id=product.id, action="CREATED", after={"code": product.code, "import_job_id": job.id})
                elif job.allow_updates:
                    changes = {field: data[field] for field in ("name", "is_active") if data.get(field) is not None}
                    if data.get("brand") is not None:
                        changes["brand_id"] = catalog_record(Brand, data["brand"], "Brand", db).id
                    if data.get("category") is not None:
                        changes["category_id"] = catalog_record(ProductCategory, data["category"], "Category", db).id
                    before = {field: getattr(product, field) for field in changes}
                    for field, value in changes.items(): setattr(product, field, value)
                    if changes: record_audit(db, actor_id=current_user.id, entity_type="product", entity_id=product.id, action="UPDATED", before=before, after=changes)
                else: raise ValueError(f"Product {data['code']} now conflicts with an existing record")
                if data.get("duration_days") is not None:
                    rule = ProductRepurchaseRule(product_id=product.id, duration_days=data["duration_days"], alert_days=data["alert_days"], effective_from=date.fromisoformat(data["effective_from"]), created_by_user_id=current_user.id)
                    db.add(rule); db.flush(); record_audit(db, actor_id=current_user.id, entity_type="product_rule", entity_id=rule.id, action="CREATED", after={"product_id": product.id, "import_job_id": job.id})
        job.state = "COMMITTED"; job.committed_at = datetime.now(timezone.utc)
        record_audit(db, actor_id=current_user.id, entity_type="import_job", entity_id=job.id, action="COMMITTED", after={"total_rows": job.total_rows})
        db.commit()
    except Exception as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Import could not be committed atomically: {error}") from error
    return job_response(job, db)
