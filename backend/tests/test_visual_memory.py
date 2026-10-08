import cv2
import numpy as np

from app.services.visual_memory import resolve_from_visual_memory, signature_for_detection


def test_confirmed_pack_can_be_matched_by_visual_memory(tmp_path) -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[20:80, 20:80] = (190, 35, 25)  # a distinctive blue-ish BGR pack
    image_path = tmp_path / "shelf.jpg"
    assert cv2.imwrite(str(image_path), image)
    detection = {"x1": 20, "y1": 20, "x2": 80, "y2": 80, "confidence": 0.9}
    signature = signature_for_detection(image_path, detection)
    products = [{"sku": "PRODUCT-TEST", "visual_signatures": [signature]}]
    future_detection = {**detection, "excluded": False}

    resolve_from_visual_memory([future_detection], products, image_path)

    assert future_detection["resolved_sku"] == "PRODUCT-TEST"
    assert future_detection["resolution_source"] == "review_memory"
