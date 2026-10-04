"""Restock alerts are persisted and deduplicated until someone resolves them."""

from datetime import datetime, timezone
import uuid

from ..db import database


async def create_restock_alerts(audit: dict) -> list[dict]:
    alerts: list[dict] = []
    active_keys = {
        f"{audit['store_id']}:{audit['shelf_id']}:{item['row']}:{item['sku']}"
        for item in audit["analysis"]["restock_candidates"]
    }
    # A later audit that shows adequate stock closes only alerts for this shelf.
    # This preserves a human acknowledgement as evidence while avoiding stale reminders.
    await database.database.alerts.update_many(
        {
            "store_id": audit["store_id"],
            "shelf_id": audit["shelf_id"],
            "status": {"$in": ["open", "acknowledged"]},
            "alert_key": {"$nin": list(active_keys)},
        },
        {
            "$set": {
                "status": "resolved",
                "resolved_by": "system_recheck",
                "resolution_note": "A later shelf audit met the configured minimum facings.",
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    for item in audit["analysis"]["restock_candidates"]:
        alert_key = f"{audit['store_id']}:{audit['shelf_id']}:{item['row']}:{item['sku']}"
        existing = await database.database.alerts.find_one(
            {"alert_key": alert_key, "status": {"$in": ["open", "acknowledged"]}}
        )
        if existing:
            alerts.append(existing)
            continue
        alert = {
            "_id": str(uuid.uuid4()),
            "alert_key": alert_key,
            "audit_id": audit["_id"],
            "store_id": audit["store_id"],
            "shelf_id": audit["shelf_id"],
            "status": "open",
            "created_at": datetime.now(timezone.utc),
            **item,
        }
        await database.database.alerts.insert_one(alert)
        alerts.append(alert)
    return alerts
