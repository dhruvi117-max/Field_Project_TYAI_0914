import asyncio
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app.services import evidence


def test_evidence_bundle_contains_visual_and_machine_readable_records(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        evidence,
        "get_settings",
        lambda: SimpleNamespace(audit_artifact_dir=str(tmp_path / "artifacts")),
    )
    source = tmp_path / "source.png"
    annotated = tmp_path / "annotated.jpg"
    Image.new("RGB", (100, 80), "white").save(source)
    Image.new("RGB", (100, 80), "white").save(annotated)
    audit = {
        "_id": "audit-1",
        "store_id": "store",
        "shelf_id": "shelf",
        "annotated_image": annotated.name,
        "analysis": {
            "detection_count": 1,
            "row_count": 1,
            "review_required": True,
            "mismatches": [],
        },
        "detections": [{
            "detection_id": "detection-1",
            "x1": 10,
            "y1": 10,
            "x2": 40,
            "y2": 50,
            "confidence": 0.9,
            "row": 1,
            "ocr_text": None,
            "resolved_sku": None,
        }],
    }

    artifacts = asyncio.run(evidence.write_evidence_bundle(audit, source, annotated))

    directory = tmp_path / "artifacts" / "audit-1"
    assert (directory / "summary.json").is_file()
    assert (directory / "report.html").is_file()
    assert (directory / "annotated.jpg").is_file()
    assert len(list((directory / "crops").glob("*.jpg"))) == 1
    assert artifacts["report_url"] == "/evidence/audit-1/report.html"
    assert audit["detections"][0]["crop_url"].endswith(".jpg")
