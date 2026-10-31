import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import admin, analytics, auth, chat, documents, faqs, files, products, research, users, voice
from app.core.config import get_settings
from app.core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bui")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.rag.indexer import ensure_index_consistency
    from app.services.bootstrap import ensure_initial_admin, ensure_roles
    from app.workers import jobs

    if settings.environment == "production" and (settings.secret_key.startswith("change-me") or settings.secret_key.startswith("replace-with") or len(settings.secret_key) < 32):
        raise RuntimeError("SECRET_KEY must be set to a long random value in production (see .env.example)")
    db = SessionLocal()
    try:
        ensure_roles(db)
        ensure_initial_admin(db)
        ensure_index_consistency(db)
    finally:
        db.close()
    jobs.start_scheduler()
    log.info("BUI API ready")
    yield
    jobs.shutdown()


app = FastAPI(
    title="BUI – Business Unified Intelligence API",
    version="1.0.0",
    description="Your Intelligent Business & Product Assistant.",
    lifespan=lifespan,
    docs_url=f"{settings.api_prefix}/docs",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    limit = (settings.max_upload_mb + 1) * 1024 * 1024
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > limit:
        return JSONResponse({"detail": f"Request too large (max {settings.max_upload_mb} MB)"}, status_code=413)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


for r in (auth, users, products, documents, faqs, files, chat, research, analytics, admin, voice):
    app.include_router(r.router, prefix=settings.api_prefix)


@app.get(f"{settings.api_prefix}/health", tags=["system"])
def health():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "app": "BUI"}
    except Exception:
        return JSONResponse({"status": "degraded"}, status_code=503)
    finally:
        db.close()
