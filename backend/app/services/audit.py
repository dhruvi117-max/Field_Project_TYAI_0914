"""Confidence-aware shelf-row, product-resolution and planogram analysis."""

from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from .visual_memory import resolve_from_visual_memory


def normalise(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def assign_shelf_rows(detections: list[dict], image_height: int) -> list[dict]:
    """Cluster box centres vertically. This simple, explainable baseline suits a student project."""
    usable = [item for item in detections if not item.get("excluded")]
    usable.sort(key=lambda item: (item["y1"] + item["y2"]) / 2)
    tolerance = max(35, round(image_height * 0.04))
    row_centres: list[float] = []
    for detection in usable:
        centre = (detection["y1"] + detection["y2"]) / 2
        if not row_centres or abs(centre - row_centres[-1]) > tolerance:
            row_centres.append(centre)
        else:
            previous = row_centres[-1]
            row_centres[-1] = (previous + centre) / 2
        detection["row"] = len(row_centres)
    return usable


def resolve_product_labels(detections: list[dict], products: list[dict]) -> list[dict]:
    """Map OCR to a locally managed product catalogue; ambiguous OCR stays unresolved."""
    aliases: list[tuple[str, str]] = []
    for product in products:
        for alias in [product["sku"], product["name"], *product.get("ocr_aliases", [])]:
            cleaned = normalise(alias)
            if cleaned:
                aliases.append((cleaned, product["sku"]))

    for detection in detections:
        if detection.get("excluded") or detection.get("resolved_sku"):
            continue
        text = normalise(detection.get("ocr_text") or "")
        if len(text) < 3:
            continue
        candidate_sku, score = None, 0.0
        for alias, sku in aliases:
            similarity = SequenceMatcher(None, text, alias).ratio()
            if alias in text or text in alias:
                similarity = max(similarity, 0.88)
            if similarity > score:
                candidate_sku, score = sku, similarity
        # This deliberately conservative threshold avoids unsafe planogram claims from OCR noise.
        if candidate_sku and score >= 0.82:
            detection["resolved_sku"] = candidate_sku
            detection["resolution_source"] = "ocr_catalogue"
            detection["resolution_score"] = round(score, 3)
    return detections


def analyse_planogram(
    detections: list[dict],
    planogram: dict,
    products: list[dict],
    image_height: int,
    min_confidence: float,
    image_width: int = 0,
    source_image_path: Path | None = None,
) -> dict:
    assigned = assign_shelf_rows(detections, image_height)
    resolve_product_labels(assigned, products)
    resolve_from_visual_memory(assigned, products, source_image_path)
    high_confidence = [item for item in assigned if item["confidence"] >= min_confidence]
    labelled = [item for item in high_confidence if item.get("resolved_sku")]
    observed = Counter((item["row"], item["resolved_sku"]) for item in labelled)
    slots = planogram["slots"]
    expected_keys = {(slot["row"], slot["sku"]) for slot in slots}
    mismatches: list[dict] = []
    alerts: list[dict] = []
    for slot in slots:
        key = (slot["row"], slot["sku"])
        count = observed.get(key, 0)
        shortfall = max(0, slot["expected_facings"] - count)
        if shortfall:
            restock_needed = count < slot["minimum_facings"]
            mismatch = {
                "type": "restock" if restock_needed else "facing_shortfall",
                "row": slot["row"],
                "sku": slot["sku"],
                "product_name": slot.get("product_name", slot["sku"]),
                "expected_facings": slot["expected_facings"],
                "minimum_facings": slot["minimum_facings"],
                "observed_facings": count,
                "shortfall": shortfall,
                "needs_restock": restock_needed,
            }
            mismatches.append(mismatch)
            if restock_needed:
                alerts.append({**mismatch, "severity": "critical" if count == 0 else "warning"})

    for item in labelled:
        if (item["row"], item["resolved_sku"]) not in expected_keys:
            mismatches.append(
                {
                    "type": "unexpected_product",
                    "row": item["row"],
                    "sku": item["resolved_sku"],
                    "detection_id": item["detection_id"],
                    "needs_restock": False,
                }
            )
            continue

    confidence_values = [item["confidence"] for item in assigned]
    unresolved = [item for item in high_confidence if not item.get("resolved_sku")]
    confidence_breakdown = {
        "high": sum(item["confidence"] >= 0.75 for item in assigned),
        "medium": sum(0.5 <= item["confidence"] < 0.75 for item in assigned),
        "low": sum(item["confidence"] < 0.5 for item in assigned),
    }
    row_summaries = [
        {
            "row": row,
            "detections": len([item for item in assigned if item["row"] == row]),
            "confirmed_skus": len([item for item in labelled if item["row"] == row]),
            "needs_review": len([item for item in unresolved if item["row"] == row]),
        }
        for row in range(1, max((item["row"] for item in assigned), default=0) + 1)
    ]
    # A potentially empty facing cannot be called a restock issue while the
    # system still has unnamed high-confidence products in the same photograph.
    # The candidate list is preserved for explanation, but alerts are deferred
    # until the reviewer completes the audit.
    review_required = bool(unresolved)
    return {
        "row_count": max((item["row"] for item in assigned), default=0),
        "detection_count": len(assigned),
        "high_confidence_detection_count": len(high_confidence),
        "unresolved_detection_count": len(unresolved),
        "average_detection_confidence": round(sum(confidence_values) / len(confidence_values), 3)
        if confidence_values
        else 0.0,
        "confidence_breakdown": confidence_breakdown,
        "row_summaries": row_summaries,
        "mismatches": mismatches,
        "restock_candidates": [] if review_required else alerts,
        "pending_restock_candidates": alerts if review_required else [],
        "restock_ready": not review_required,
        "restock_blocked_by_review": review_required and bool(alerts),
        "review_required": review_required,
        "review_reason": "Some detected products could not be safely matched to a catalogue SKU."
        " Restock reminders will be calculated after human review."
        if review_required
        else None,
    }
