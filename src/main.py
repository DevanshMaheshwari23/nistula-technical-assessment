from __future__ import annotations
import logging, time, uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.core.config import get_settings
from src.core.logging import configure_logging
from src.routes.webhook import router as webhook_router

configure_logging()
logger   = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Nistula starting — env={settings.app_env} model={settings.claude_model}")
    yield
    logger.info("Shutdown.")


app = FastAPI(
    title="Nistula Guest Message Handler",
    version="1.0.0", lifespan=lifespan, docs_url="/docs", redoc_url="/redoc",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET","POST"],
                   allow_headers=["Content-Type"])


@app.middleware("http")
async def timing(request: Request, call_next):
    t0 = time.monotonic()
    r  = await call_next(request)
    r.headers["X-Process-Time-Ms"] = str(int((time.monotonic()-t0)*1000))
    return r


@app.exception_handler(RequestValidationError)
async def val_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "validation_error",
                               "details": [{"field": ".".join(str(l) for l in e["loc"] if l!="body"),
                                            "message": e["msg"]} for e in exc.errors()]})

app.include_router(webhook_router)


@app.get("/health", tags=["Ops"])
async def health():
    return {"status": "ok", "service": "nistula-messaging", "version": "1.0.0",
            "environment": settings.app_env, "model": settings.claude_model}

@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({"service": "Nistula Guest Message Handler", "docs": "/docs"})