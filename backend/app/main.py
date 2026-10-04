"""FastAPI entry point. Serves the supplied static report at http://localhost:8000/."""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core import get_settings
from .db import database
from .observability import increment, log_event, observe_seconds, trace_id
from .routers.api import router

PROJECT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_FILE = PROJECT_DIR / "Retail Shelf Intelligence — Visual Analytics Report.html"
LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await database.connect()
    except Exception as error:
        # Keep the dashboard and health endpoint available so a missing MongoDB instance is diagnosable.
        LOGGER.error("MongoDB startup check failed: %s", error)
    try:
        yield
    finally:
        await database.disconnect()


app = FastAPI(title="Retail Shelf Intelligence API", version="1.1.0",
              description="Confidence-aware shelf audits, planogram checks and restock alerts.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origin_list, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "OPTIONS"], allow_headers=["Content-Type", "X-API-Key", "X-User-Role", "X-Request-ID"])
app.include_router(router)
UPLOAD_DIR = Path(get_settings().upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
ARTIFACT_DIR = Path(get_settings().audit_artifact_dir)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/evidence", StaticFiles(directory=str(ARTIFACT_DIR)), name="evidence")


@app.middleware("http")
async def trace_and_measure_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    context_token = trace_id.set(request_id)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        increment("http_requests_total")
        increment("http_server_errors_total")
        observe_seconds("http_request", time.perf_counter() - started_at)
        log_event("request_failed", method=request.method, path=request.url.path)
        raise
    else:
        duration = time.perf_counter() - started_at
        increment("http_requests_total")
        if response.status_code >= 400:
            increment("http_client_or_server_errors_total")
        observe_seconds("http_request", duration)
        response.headers["X-Request-ID"] = request_id
        log_event(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration * 1000),
        )
        return response
    finally:
        trace_id.reset(context_token)


@app.get("/", include_in_schema=False)
async def report() -> FileResponse:
    return FileResponse(FRONTEND_FILE, media_type="text/html")
