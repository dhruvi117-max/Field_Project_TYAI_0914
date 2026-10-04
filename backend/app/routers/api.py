from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import PlainTextResponse

from ..core import get_settings
from ..db import database
from ..observability import increment, log_event, observe_seconds, trace_id
from ..rate_limit import limit_audit_requests
from ..schemas import AlertActionIn, HealthOut, OverrideIn, PlanogramIn, ProductIn
from ..security import require_api_key, require_auditor
from ..services.alerts import create_restock_alerts
from ..services.audit import analyse_planogram
from ..services.evidence import refresh_evidence_report, write_evidence_bundle
from ..services.inference import ModelNotReadyError, inference_engine

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
WRITE_GUARD = [Depends(require_auditor)]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
LOGGER = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def write_event(audit_id: str, event_type: str, actor: str, details: dict) -> None:
    await database.database.audit_events.insert_one(
        {"_id": str(uuid.uuid4()), "audit_id": audit_id, "event_type": event_type,
         "actor": actor, "details": details, "trace_id": trace_id.get(), "created_at": utc_now()}
    )


def validate_image_contents(contents: bytes) -> tuple[int, int]:
    """Verify the bytes are a decodable image before writing them to disk."""
    try:
        from PIL import Image, UnidentifiedImageError

        with Image.open(BytesIO(contents)) as candidate:
            candidate.verify()
        with Image.open(BytesIO(contents)) as candidate:
            width, height = candidate.size
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid decodable image.") from error
    if not width or not height:
        raise HTTPException(status_code=415, detail="The uploaded image has invalid dimensions.")
    maximum = get_settings().max_image_dimension
    if width > maximum or height > maximum:
        raise HTTPException(
            status_code=413,
            detail=f"Image dimensions exceed the {maximum}px safety limit.",
        )
    return width, height


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    try:
        await database.database.command("ping")
        connected = "connected"
    except Exception:
        connected = "disconnected"
    return HealthOut(status="ok" if connected == "connected" and inference_engine.is_ready else "degraded",
                     database=connected, model_ready=inference_engine.is_ready, timestamp=utc_now())


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    """Operational evidence endpoint; scrape only inside the trusted demo network."""
    from ..observability import prometheus_metrics

    return prometheus_metrics()


@router.post("/products", status_code=status.HTTP_201_CREATED, dependencies=WRITE_GUARD)
async def create_product(product: ProductIn) -> dict:
    record = {"_id": product.sku, **product.model_dump(mode="json"), "created_at": utc_now()}
    try:
        await database.database.products.insert_one(record)
    except Exception as error:
        if "duplicate key" in str(error).lower():
            raise HTTPException(status_code=409, detail="A product with this SKU already exists") from error
        raise
    return record


@router.get("/products")
async def list_products() -> list[dict]:
    return await database.database.products.find({}, {"_id": 0}).sort("sku", 1).to_list(length=1000)


@router.put("/planograms/{store_id}/{shelf_id}", dependencies=WRITE_GUARD)
async def upsert_planogram(store_id: str, shelf_id: str, planogram: PlanogramIn) -> dict:
    if (store_id, shelf_id) != (planogram.store_id, planogram.shelf_id):
        raise HTTPException(status_code=400, detail="URL and request store/shelf identifiers must agree")
    for slot in planogram.slots:
        if slot.minimum_facings > slot.expected_facings:
            raise HTTPException(status_code=422, detail="minimum_facings cannot exceed expected_facings")
    record = {"_id": f"{store_id}:{shelf_id}", **planogram.model_dump(), "updated_at": utc_now()}
    await database.database.planograms.replace_one({"_id": record["_id"]}, record, upsert=True)
    return record


@router.get("/planograms/{store_id}/{shelf_id}")
async def get_planogram(store_id: str, shelf_id: str) -> dict:
    planogram = await database.database.planograms.find_one({"_id": f"{store_id}:{shelf_id}"}, {"_id": 0})
    if not planogram:
        raise HTTPException(status_code=404, detail="Planogram not found")
    return planogram


@router.post(
    "/audits",
    status_code=status.HTTP_201_CREATED,
    dependencies=[*WRITE_GUARD, Depends(limit_audit_requests)],
)
async def create_audit(
    request: Request,
    image: UploadFile = File(...),
    store_id: str = Form(...),
    shelf_id: str = Form(...),
    operator: str = Form(...),
) -> dict:
    started_at = time.perf_counter()
    suffix = Path(image.filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise HTTPException(status_code=415, detail="Upload JPG, JPEG, PNG or WEBP images only")
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded image is empty")
    if len(contents) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image exceeds {get_settings().max_upload_mb} MB limit")
    claimed_type = (image.content_type or "").lower()
    if claimed_type and not claimed_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="The upload content type must be an image.")
    validate_image_contents(contents)
    planogram = await database.database.planograms.find_one({"_id": f"{store_id}:{shelf_id}"})
    if not planogram:
        raise HTTPException(status_code=404, detail="Create a planogram for this store and shelf before auditing")
    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    audit_id = str(uuid.uuid4())
    saved_path = upload_dir / f"{audit_id}_source{suffix}"
    saved_path.write_bytes(contents)
    inference_started_at = time.perf_counter()
    try:
        detections, image_width, image_height = await inference_engine.predict(saved_path)
    except ModelNotReadyError as error:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(error)) from error
    inference_ms = round((time.perf_counter() - inference_started_at) * 1000)
    observe_seconds("inference", inference_ms / 1000)
    annotated_path = upload_dir / f"{audit_id}_detected.jpg"
    try:
        await inference_engine.render_annotated_image(saved_path, detections, annotated_path)
    except Exception as error:
        # A visual artifact improves the review experience but must never discard a completed audit.
        LOGGER.exception("Could not render annotated audit image: %s", error)
        annotated_path = None
    products = await database.database.products.find({}, {"_id": 0}).to_list(length=1000)
    analysis = analyse_planogram(
        detections,
        planogram,
        products,
        image_height,
        get_settings().min_detection_confidence,
        image_width,
    )
    audit = {"_id": audit_id, "store_id": store_id, "shelf_id": shelf_id, "operator": operator,
             "created_at": utc_now(), "source_image": saved_path.name, "source_image_url": f"/uploads/{saved_path.name}",
             "annotated_image": annotated_path.name if annotated_path else None,
             "annotated_image_url": f"/uploads/{annotated_path.name}" if annotated_path else None,
             "image_width": image_width, "image_height": image_height,
             "planogram_snapshot": {key: value for key, value in planogram.items() if key != "_id"}, "detections": detections,
             "analysis": analysis, "trace_id": trace_id.get(),
             "timings_ms": {"inference": inference_ms},
             "status": "needs_review" if analysis["review_required"] else "completed"}
    try:
        audit["artifacts"] = await write_evidence_bundle(audit, saved_path, annotated_path)
    except Exception as error:
        # The audit is still valid if an optional evidence file cannot be produced.
        LOGGER.exception("Could not write evidence bundle for audit %s: %s", audit_id, error)
        audit["artifacts"] = {}
    await database.database.audits.insert_one(audit)
    await write_event(audit["_id"], "audit_created", operator, {"detections": len(detections)})
    audit["alerts"] = await create_restock_alerts(audit)
    audit["timings_ms"]["total"] = round((time.perf_counter() - started_at) * 1000)
    await database.database.audits.update_one(
        {"_id": audit_id},
        {"$set": {"alerts": audit["alerts"], "timings_ms": audit["timings_ms"]}},
    )
    try:
        audit["artifacts"] = await refresh_evidence_report(audit)
    except Exception as error:
        LOGGER.warning("Could not refresh evidence report for audit %s: %s", audit_id, error)
    increment("audits_total")
    observe_seconds("audit_total", audit["timings_ms"]["total"] / 1000)
    log_event(
        "audit_completed",
        audit_id=audit_id,
        store_id=store_id,
        shelf_id=shelf_id,
        detections=len(detections),
        processing_ms=audit["timings_ms"]["total"],
        client=request.client.host if request.client else "unknown",
    )
    return audit


@router.get("/audits")
async def list_audits(
    limit: int = Query(default=20, ge=1, le=100),
    store_id: str | None = Query(default=None),
    shelf_id: str | None = Query(default=None),
) -> list[dict]:
    query = {key: value for key, value in {"store_id": store_id, "shelf_id": shelf_id}.items() if value}
    return await database.database.audits.find(query, {"detections": 0}).sort("created_at", -1).to_list(length=limit)


@router.get("/audits/{audit_id}")
async def get_audit(audit_id: str) -> dict:
    audit = await database.database.audits.find_one({"_id": audit_id})
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    audit["events"] = await database.database.audit_events.find({"audit_id": audit_id}).sort("created_at", 1).to_list(length=1000)
    return audit


@router.post("/audits/{audit_id}/overrides", dependencies=WRITE_GUARD)
async def override_detection(audit_id: str, override: OverrideIn) -> dict:
    audit = await database.database.audits.find_one({"_id": audit_id})
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    detection = next((item for item in audit["detections"] if item["detection_id"] == override.detection_id), None)
    if detection is None:
        raise HTTPException(status_code=404, detail="Detection not found in this audit")
    if override.action == "remove":
        detection.update({"excluded": True, "resolved_sku": None, "resolution_source": "human_removed"})
    else:
        if not override.corrected_sku:
            raise HTTPException(status_code=422, detail="corrected_sku is required when confirming or correcting")
        product = await database.database.products.find_one({"sku": override.corrected_sku})
        if not product:
            raise HTTPException(status_code=422, detail="corrected_sku is not in the product catalogue")
        detection.update({"resolved_sku": override.corrected_sku, "resolution_source": "human_confirmed", "excluded": False})
    planogram = {"slots": audit["planogram_snapshot"]["slots"]}
    products = await database.database.products.find({}, {"_id": 0}).to_list(length=1000)
    audit["analysis"] = analyse_planogram(
        audit["detections"],
        planogram,
        products,
        audit["image_height"],
        get_settings().min_detection_confidence,
        audit.get("image_width", 0),
    )
    audit["status"] = "needs_review" if audit["analysis"]["review_required"] else "completed"
    await database.database.audits.replace_one({"_id": audit_id}, audit)
    await write_event(audit_id, "human_override", override.reviewer, override.model_dump())
    audit["alerts"] = await create_restock_alerts(audit)
    audit["artifacts"] = await refresh_evidence_report(audit)
    await database.database.audits.update_one(
        {"_id": audit_id},
        {"$set": {"analysis": audit["analysis"], "status": audit["status"], "detections": audit["detections"], "alerts": audit["alerts"], "artifacts": audit["artifacts"]}},
    )
    log_event("human_override", audit_id=audit_id, action=override.action, reviewer=override.reviewer)
    return audit


@router.get("/alerts")
async def list_alerts(status_filter: str = Query(default="open", alias="status")) -> list[dict]:
    query = {} if status_filter == "all" else {"status": status_filter}
    return await database.database.alerts.find(query).sort("created_at", -1).to_list(length=200)


@router.post("/alerts/{alert_id}/action", dependencies=WRITE_GUARD)
async def act_on_alert(alert_id: str, action: AlertActionIn) -> dict:
    alert = await database.database.alerts.find_one({"_id": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert["status"] = "acknowledged" if action.action == "acknowledge" else "resolved"
    alert.update({"updated_at": utc_now(), "updated_by": action.actor, "resolution_note": action.note})
    await database.database.alerts.replace_one({"_id": alert_id}, alert)
    await write_event(alert["audit_id"], f"alert_{action.action}d", action.actor, {"alert_id": alert_id, "note": action.note})
    return alert
