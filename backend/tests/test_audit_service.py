from app.services.audit import analyse_planogram


def detection(identifier: str, y: int, sku: str | None, confidence: float = 0.9) -> dict:
    return {
        "detection_id": identifier, "label": "object", "confidence": confidence,
        "x1": 10, "x2": 50, "y1": y, "y2": y + 40,
        "resolved_sku": sku, "excluded": False,
    }


def test_planogram_creates_restock_alert_for_empty_required_slot() -> None:
    planogram = {"slots": [
        {"row": 1, "sku": "A", "expected_facings": 2, "minimum_facings": 1},
        {"row": 2, "sku": "B", "expected_facings": 1, "minimum_facings": 1},
    ]}
    result = analyse_planogram([detection("one", 10, "A")], planogram, [], 600, 0.35)
    assert result["row_count"] == 1
    assert result["restock_candidates"] == [{
        "type": "restock", "row": 2, "sku": "B", "expected_facings": 1,
        "minimum_facings": 1, "observed_facings": 0, "shortfall": 1,
        "needs_restock": True, "position_hint": None, "severity": "critical",
    }]


def test_unresolved_detection_requires_human_review() -> None:
    planogram = {"slots": [{"row": 1, "sku": "A", "expected_facings": 1, "minimum_facings": 1}]}
    result = analyse_planogram([detection("one", 10, None)], planogram, [], 600, 0.35)
    assert result["review_required"] is True
    assert result["unresolved_detection_count"] == 1


def test_position_hint_creates_explainable_position_deviation() -> None:
    planogram = {
        "slots": [{"row": 1, "sku": "A", "expected_facings": 1, "minimum_facings": 0, "position_hint": "right"}]
    }
    result = analyse_planogram([detection("one", 10, "A")], planogram, [], 600, 0.35, image_width=900)
    assert result["mismatches"] == [{
        "type": "position_deviation", "row": 1, "sku": "A", "detection_id": "one",
        "expected_position": "right", "observed_position": "left", "needs_restock": False,
    }]


def test_excluded_detection_does_not_create_a_false_facing_count() -> None:
    planogram = {"slots": [{"row": 1, "sku": "A", "expected_facings": 1, "minimum_facings": 1}]}
    removed = detection("one", 10, "A")
    removed["excluded"] = True
    result = analyse_planogram([removed], planogram, [], 600, 0.35)
    assert result["detection_count"] == 0
    assert result["restock_candidates"][0]["observed_facings"] == 0
