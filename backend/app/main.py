import logging
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.middleware import ApiMiddleware

logger = logging.getLogger("arctic.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Арктика — API конкурса",
    version="1.0.0",
    description="Участники, тестирование, проекты, экспертиза и управление конкурсом. Все даты — ISO 8601 с часовым поясом.",
    lifespan=lifespan,
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)
if settings.environment == "production":
    hosts = {"localhost", "127.0.0.1", "api"}
    hosts.update(filter(None, (urlsplit(origin).hostname for origin in settings.allowed_origins)))
    hosts.add(urlsplit(settings.public_base_url).hostname or "localhost")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=sorted(hosts))
app.add_middleware(ApiMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
)


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse({"detail": "Операция конфликтует с существующими данными"}, status_code=409)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logger.error("Database operation failed: %s", type(exc).__name__)
    return JSONResponse({"detail": "База данных временно недоступна"}, status_code=503)


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse("/docs")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "version": app.version}


@app.get("/health/ready", tags=["health"])
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
    return {"status": "ready", "database": "postgresql"}


from app import admin, assistant, auth, avatars, certificates, comments, content, projects, quiz, reviews  # noqa: E402

for module in (auth, avatars, content, quiz, certificates, projects, reviews, admin, assistant, comments):
    app.include_router(module.router, prefix="/api/v1")
