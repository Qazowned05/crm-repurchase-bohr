from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.modules.auth.routes import router as auth_router
from app.modules.customers.routes import router as customers_router
from app.modules.products.routes import router as products_router
from app.modules.imports.routes import router as imports_router
from app.modules.sales.routes import router as sales_router
from app.modules.alerts.routes import router as alerts_router
from app.modules.users.routes import router as users_router
from app.modules.supervision.routes import router as supervision_router
from app.modules.reports.routes import router as reports_router

app = FastAPI(title="CRM Fidelizacion API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(customers_router)
app.include_router(products_router)
app.include_router(imports_router)
app.include_router(sales_router)
app.include_router(alerts_router)
app.include_router(supervision_router)
app.include_router(reports_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
