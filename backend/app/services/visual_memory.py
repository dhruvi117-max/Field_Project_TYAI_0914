"""Small, conservative visual memory for products confirmed by a reviewer.

This is intentionally not presented as online YOLO training.  YOLO still finds
product facings; this module stores a compact colour/layout signature of a crop
after a human names it and can recognise a sufficiently similar pack later.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


MEMORY_THRESHOLD = 0.93


def _signature(image: np.ndarray, detection: dict) -> list[float] | None:
    height, width = image.shape[:2]
    x1 = max(0, min(width - 1, int(detection.get("x1", 0))))
    y1 = max(0, min(height - 1, int(detection.get("y1", 0))))
    x2 = max(x1 + 1, min(width, int(detection.get("x2", width))))
    y2 = max(y1 + 1, min(height, int(detection.get("y2", height))))
    crop = image[y1:y2, x1:x2]
    if crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 8:
        return None
    crop = cv2.resize(crop, (64, 64), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1, 2], None, [12, 4, 4], [0, 180, 0, 256, 0, 256])
    histogram = cv2.normalize(histogram, histogram).flatten()
    return [round(float(value), 7) for value in histogram]


def signature_for_detection(image_path: Path, detection: dict) -> list[float] | None:
    image = cv2.imread(str(image_path))
    return _signature(image, detection) if image is not None else None


def resolve_from_visual_memory(
    detections: list[dict], products: list[dict], image_path: Path | None
) -> list[dict]:
    """Resolve only near-identical packs; uncertain matches remain for review."""
    if image_path is None:
        return detections
    image = cv2.imread(str(image_path))
    if image is None:
        return detections
    known: list[tuple[str, np.ndarray]] = []
    for product in products:
        for sample in product.get("visual_signatures", []):
            vector = np.asarray(sample, dtype=np.float32)
            if vector.size:
                known.append((product["sku"], vector / max(float(np.linalg.norm(vector)), 1e-8)))
    if not known:
        return detections
    for detection in detections:
        if detection.get("excluded") or detection.get("resolved_sku"):
            continue
        signature = _signature(image, detection)
        if not signature:
            continue
        vector = np.asarray(signature, dtype=np.float32)
        vector = vector / max(float(np.linalg.norm(vector)), 1e-8)
        sku, score = max(((sku, float(np.dot(vector, sample))) for sku, sample in known), key=lambda item: item[1])
        if score >= MEMORY_THRESHOLD:
            detection.update(
                {
                    "resolved_sku": sku,
                    "resolution_source": "review_memory",
                    "resolution_score": round(score, 3),
                }
            )
    return detections
