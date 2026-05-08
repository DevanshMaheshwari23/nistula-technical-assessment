"""
FastAPI application entry point.
Run: uvicorn src.main:app --reload --port 8000
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from src.config import get_settings
from src.routes.webhook import router as webhook_router
from src.utils.logger import setup_logging

settings = get_settings()
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting — env=%s model=%s", settings.app_env, settings.claude_model)
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Nistula Guest Message Handler",
    description="AI-powered guest messaging for Nistula Villas, Goa.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"field": " -> ".join(str(l) for l in e["loc"] if l != "body"),
         "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422,
                        content={"error": "validation_error", "details": errors})


app.include_router(webhook_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "nistula-messaging", "version": "1.0.0",
            "environment": settings.app_env}


@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({"message": "Running.", "docs": "/docs",
                         "webhook": "POST /webhook/message"})