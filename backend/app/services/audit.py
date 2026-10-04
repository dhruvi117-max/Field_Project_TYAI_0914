"""Confidence-aware shelf-row, product-resolution and planogram analysis."""

from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher


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


def _position_band(item: dict, image_width: int) -> str | None:
    if image_width <= 0:
        return None
    centre = (item["x1"] + item["x2"]) / 2
    proportion = centre / image_width
    if proportion < 1 / 3:
        return "left"
    if proportion > 2 / 3:
        return "right"
    return "centre"


def _normalised_position_hint(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().lower().replace("center", "centre")
    return cleaned if cleaned in {"left", "centre", "right"} else None


def analyse_planogram(
    detections: list[dict],
    planogram: dict,
    products: list[dict],
    image_height: int,
    min_confidence: float,
    image_width: int = 0,
) -> dict:
    assigned = assign_shelf_rows(detections, image_height)
    resolve_product_labels(assigned, products)
    high_confidence = [item for item in assigned if item["confidence"] >= min_confidence]
    labelled = [item for item in high_confidence if item.get("resolved_sku")]
    observed = Counter((item["row"], item["resolved_sku"]) for item in labelled)
    slots = planogram["slots"]
    expected_keys = {(slot["row"], slot["sku"]) for slot in slots}
    slot_by_key = {(slot["row"], slot["sku"]): slot for slot in slots}
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
                "expected_facings": slot["expected_facings"],
                "minimum_facings": slot["minimum_facings"],
                "observed_facings": count,
                "shortfall": shortfall,
                "needs_restock": restock_needed,
                "position_hint": slot.get("position_hint"),
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
        slot = slot_by_key[(item["row"], item["resolved_sku"])]
        expected_position = _normalised_position_hint(slot.get("position_hint"))
        observed_position = _position_band(item, image_width)
        if expected_position and observed_position and expected_position != observed_position:
            mismatches.append(
                {
                    "type": "position_deviation",
                    "row": item["row"],
                    "sku": item["resolved_sku"],
                    "detection_id": item["detection_id"],
                    "expected_position": expected_position,
                    "observed_position": observed_position,
                    "needs_restock": False,
                }
            )

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
        "restock_candidates": alerts,
        "review_required": bool(unresolved),
        "review_reason": "Some detected products could not be safely matched to a catalogue SKU."
        if unresolved
        else None,
    }
