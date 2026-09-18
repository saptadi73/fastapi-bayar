import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.client_payments import router as client_router
from app.api.v1.public_checkout import router as public_router
from app.api.v1.webhooks import router as webhook_router
from app.api.v1.auth import router as auth_router
from app.api.v1.admin import router as admin_router
from app.api.v1.admin_clients import router as admin_clients_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.admin_services import router as admin_services_router
from app.api.v1.admin_payments import router as admin_payments_router
from app.api.v1.admin_reconciliation import router as admin_reconciliation_router
from app.api.v1.admin_refunds import router as admin_refunds_router
from app.core.config import get_settings
from app.core.database import Base, check_database, engine
from app.core.errors import AppError
from app.models import payment  # noqa: F401

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_create_tables and settings.environment.lower() != "production":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title=get_settings().app_name, version="0.1.0", lifespan=lifespan)
static_dir = Path(__file__).parent / "static"
app.mount("/assets", StaticFiles(directory=static_dir), name="assets")


@app.get("/p/{payment_no}", include_in_schema=False)
async def checkout_page(payment_no: str):
    return FileResponse(static_dir / "checkout.html", headers={
        "Content-Security-Policy": "default-src 'none'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
        "X-Content-Type-Options": "nosniff",
    })


@app.get("/checkout-config", include_in_schema=False)
async def checkout_config():
    return {"api_prefix": get_settings().api_prefix}

@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex}")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    headers = {"Retry-After": str(exc.details["retry_after"])} if exc.status_code == 429 and exc.details and "retry_after" in exc.details else None
    return JSONResponse(status_code=exc.status_code, headers=headers, content={"error": {"code": exc.code, "message": exc.message, "request_id": request.state.request_id, "details": exc.details}})

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = [{key: value for key, value in error.items() if key in {"loc", "type", "msg"}} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "Request tidak valid", "request_id": request.state.request_id, "details": details}})

@app.get("/health", tags=["System"])
async def health():
    return {"data": {"status": "ok", "service": get_settings().app_name}}


@app.get("/health/database", tags=["System"])
async def database_health():
    try:
        result = await check_database()
        return {"data": result}
    except Exception:
        return JSONResponse(status_code=503, content={"error": {"code": "DATABASE_UNAVAILABLE", "message": "Database tidak dapat dihubungi", "request_id": "health-check", "details": None}})


@app.get("/health/ready", tags=["System"])
async def readiness():
    try:
        await check_database()
        return {"data": {"status": "ready", "database": "connected"}}
    except Exception:
        return JSONResponse(status_code=503, content={"error": {"code": "SERVICE_NOT_READY", "message": "Service belum siap karena database tidak tersedia", "request_id": "readiness-check", "details": None}})

app.include_router(client_router, prefix=get_settings().api_prefix)
app.include_router(public_router, prefix=get_settings().api_prefix)
app.include_router(webhook_router, prefix=get_settings().api_prefix)
app.include_router(auth_router, prefix=get_settings().api_prefix)
app.include_router(admin_router, prefix=get_settings().api_prefix)
app.include_router(admin_clients_router, prefix=get_settings().api_prefix)
app.include_router(admin_users_router, prefix=get_settings().api_prefix)
app.include_router(admin_services_router, prefix=get_settings().api_prefix)
app.include_router(admin_payments_router, prefix=get_settings().api_prefix)
app.include_router(admin_reconciliation_router, prefix=get_settings().api_prefix)
app.include_router(admin_refunds_router, prefix=get_settings().api_prefix)
