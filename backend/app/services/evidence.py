"""Per-audit evidence artifacts inspired by the partner pipeline's useful run folders.

Artifacts are generated from the actual API result and linked from MongoDB.  They are
not a second source of truth: the audit document remains authoritative.
"""

from __future__ import annotations

import asyncio
import html
import json
import shutil
from pathlib import Path

from ..core import get_settings


def _artifact_root() -> Path:
    root = Path(get_settings().audit_artifact_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def artifact_urls(audit_id: str, detections: list[dict]) -> dict:
    base = f"/evidence/{audit_id}"
    return {
        "directory_url": base + "/",
        "report_url": base + "/report.html",
        "summary_url": base + "/summary.json",
        "crops": [
            {
                "detection_id": item["detection_id"],
                "url": item.get("crop_url"),
            }
            for item in detections
            if item.get("crop_url")
        ],
    }


def _report_html(audit: dict) -> str:
    analysis = audit["analysis"]
    review_note = (
        "Restock reminders are deferred until every uncertain product is reviewed."
        if analysis.get("restock_blocked_by_review")
        else "Product review is complete; restock findings below are based on confirmed identities."
    )
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('detection_id', ''))[:8])}</td>"
        f"<td>{html.escape(str(item.get('row', '–')))}</td>"
        f"<td>{float(item.get('confidence', 0)):.0%}</td>"
        f"<td>{html.escape(str(item.get('ocr_text') or 'No readable text'))}</td>"
        f"<td>{html.escape(str(item.get('resolved_sku') or 'Human review needed'))}</td>"
        "</tr>"
        for item in audit["detections"]
    )
    mismatches = "".join(
        "<li>"
        f"{html.escape(str(item.get('type', 'mismatch')))} — row {html.escape(str(item.get('row', '–')))}, "
        f"{html.escape(str(item.get('sku', 'unknown')))}"
        f" ({html.escape(str(item.get('observed_facings', '–')))}/"
        f"{html.escape(str(item.get('expected_facings', '–')))} facings)"
        "</li>"
        for item in analysis.get("mismatches", [])
    ) or "<li>No planogram mismatches were found.</li>"
    annotated_markup = '<img src="annotated.jpg" alt="Annotated shelf audit">' if audit.get("annotated_image") else "<p>No annotated image was generated for this audit.</p>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Audit {html.escape(audit['_id'])}</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;color:#241b35}}h1{{color:#5a2b82}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #ddd;padding:8px;text-align:left}}
th{{background:#f1e9fb}}.meta{{color:#635975}}img{{max-width:100%;border:1px solid #ddd;border-radius:8px}}</style></head>
<body><h1>Retail Shelf Intelligence — Audit evidence</h1>
<p class="meta">Audit ID: {html.escape(audit['_id'])} · Store: {html.escape(audit['store_id'])} · Shelf: {html.escape(audit['shelf_id'])}</p>
<p>Detected facings: <b>{analysis['detection_count']}</b> · Rows: <b>{analysis['row_count']}</b> · Human review: <b>{'Yes' if analysis['review_required'] else 'No'}</b></p>
<p class="meta">{html.escape(review_note)}</p>
<h2>Annotated result</h2>{annotated_markup}
<h2>Planogram findings</h2><ul>{mismatches}</ul>
<h2>Detection evidence</h2><table><thead><tr><th>ID</th><th>Row</th><th>Confidence</th><th>OCR</th><th>Confirmed product</th></tr></thead><tbody>{rows}</tbody></table>
<p class="meta">This report is an automatically generated evidence record. Low-confidence or unreadable items require an auditor decision.</p>
</body></html>"""


def _write_bundle_sync(audit: dict, source_path: Path, annotated_path: Path | None) -> dict:
    import cv2

    audit_id = audit["_id"]
    directory = _artifact_root() / audit_id
    crops_dir = directory / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    source_suffix = source_path.suffix.lower() if source_path.suffix else ".jpg"
    shutil.copy2(source_path, directory / f"source{source_suffix}")
    if annotated_path and annotated_path.is_file():
        shutil.copy2(annotated_path, directory / "annotated.jpg")

    image = cv2.imread(str(source_path))
    if image is not None:
        height, width = image.shape[:2]
        for index, detection in enumerate(audit["detections"], start=1):
            x1 = max(0, min(width, round(float(detection["x1"]))))
            x2 = max(0, min(width, round(float(detection["x2"]))))
            y1 = max(0, min(height, round(float(detection["y1"]))))
            y2 = max(0, min(height, round(float(detection["y2"]))))
            if x2 <= x1 or y2 <= y1:
                continue
            filename = f"{index:03d}_{detection['detection_id']}.jpg"
            if cv2.imwrite(str(crops_dir / filename), image[y1:y2, x1:x2]):
                detection["crop_url"] = f"/evidence/{audit_id}/crops/{filename}"

    (directory / "summary.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    (directory / "report.html").write_text(_report_html(audit), encoding="utf-8")
    return artifact_urls(audit_id, audit["detections"])


async def write_evidence_bundle(audit: dict, source_path: Path, annotated_path: Path | None) -> dict:
    return await asyncio.to_thread(_write_bundle_sync, audit, source_path, annotated_path)


def _refresh_report_sync(audit: dict) -> dict:
    directory = _artifact_root() / audit["_id"]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    (directory / "report.html").write_text(_report_html(audit), encoding="utf-8")
    return artifact_urls(audit["_id"], audit["detections"])


async def refresh_evidence_report(audit: dict) -> dict:
    return await asyncio.to_thread(_refresh_report_sync, audit)
