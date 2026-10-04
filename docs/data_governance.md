# Data governance, provenance and reproducibility

## Dataset and model provenance

| Asset | Purpose | What to record before submission |
| --- | --- | --- |
| SKU-110K | Generic dense-shelf product-box detection | Download source, date, licence/terms review, checksum if supplied, official split file and owner approval. |
| `yolo11n.pt` | Pretrained starting point | Ultralytics/PyTorch version and checkpoint version. |
| `models/shelf_yolo.pt` | 20-epoch local baseline | Source run directory, SHA-256 checksum, training arguments, hardware and metrics. |
| Shelf demo photos | Functional demo / staged-shelf test | Written permission, capture date, location category, photographer and whether people or personal data are present. |
| Product catalogue | OCR aliases + planogram mapping | SKU owner, last verified date and a screenshot/export of the reference planogram. |

Do not use customer faces, loyalty data, employee performance data or live CCTV.
Blur/remove people from demonstration images. Do not commit permission-sensitive
photos, raw database dumps, model checkpoints or `.env` files.

## Current baseline record

The current backend model is the local `yolo11n.pt` fine-tune copied to
`models/shelf_yolo.pt`. Its recorded run is
`runs/detect/runs/train/baseline_rtx3050`:

| Field | Recorded value |
| --- | --- |
| Base model | YOLO11n pretrained |
| Dataset | `SKU-110K.yaml` |
| Requested epochs / completed epochs | 100 / 20 (manually interrupted) |
| Image size / batch | 640 / 2 |
| Hardware | NVIDIA RTX 3050 Laptop GPU, 4 GB VRAM |
| Seed | 42 |
| Final validation precision / recall | 0.88315 / 0.81543 |
| Final validation mAP50 / mAP50-95 | 0.88228 / 0.52674 |
| Untouched test precision / recall | 0.88669 / 0.81918 |
| Untouched test mAP50 / mAP50-95 | 0.89131 / 0.53455 |
| Test inference / total validation latency | 5.057 / 10.168 ms per image |

The first two metric rows are from the last row of Ultralytics `results.csv`
and are validation metrics. The test rows are from the 2,936-image SKU-110K
test evaluation run on 4 October 2026; Ultralytics skipped one corrupt image.
Do not present the 20-epoch model as a final optimised model.

## Leakage controls

1. Retain the official SKU-110K train/validation/test split.
2. Never choose epochs, confidence thresholds or image size based on the test
   split.
3. Keep near-duplicate photos from the same staged shelf in one split only.
4. Store the exact YAML, seed, package versions and model hash with each run.
5. Use new permission-cleared local shelf images only for a final robustness
   demonstration, not to replace the independent test split.

## Data dictionary and retention

The MongoDB field-level dictionary is in
[`solution_design.md`](solution_design.md). Images are kept under
`data/uploads` and per-audit evidence under `data/audit_artifacts`. For the
classroom prototype, delete demo images after grading. For any real store,
define written retention period, access roles, encrypted storage and deletion
process before capture.
