# Model card — Shelf Product Detector

## Intended use

Detect the bounding boxes of product facings in retail shelf photographs. It supports facing count and a review-assisted planogram workflow; it is not a product-identification or pricing model.

## Training design

- Base model: YOLO11s pretrained checkpoint (proposed model); YOLO11n as a lightweight baseline.
- Dataset: SKU-110K, one generic `object` class. Record the exact download date and licence approval in the final report.
- Split: use the provided train/validation/test split. The test split must not drive hyperparameter selection.
- Reproducibility: seed 42, configuration saved by Ultralytics, and `experiment_summary.json` stores run settings and metrics.

## Measured baseline evaluation

The installed baseline was evaluated once on the untouched SKU-110K test split
on 4 October 2026. It uses the 20-epoch YOLO11n run at 640 px on the NVIDIA
RTX 3050 Laptop GPU. Ultralytics skipped one corrupt test image; that fact must
be reported with the metric table.

| Measure | Baseline YOLO11n (20 epochs) | Proposed model | Acceptance target |
| --- | ---: | ---: | ---: |
| Test mAP50-95 | 0.5346 | not yet trained | improve baseline or justify trade-off |
| Test mAP50 | 0.8913 | not yet trained | report |
| Test precision | 0.8867 | not yet trained | report trade-off |
| Test recall | 0.8192 | not yet trained | report trade-off |
| Inference latency | 5.057 ms/image | not yet trained | fit demo hardware |
| End-to-end validation latency | 10.168 ms/image | not yet trained | report separately from API/OCR time |

The figures are stored in `runs/evaluation_metrics.json`. They measure generic
product-facing boxes, not SKU-identification accuracy or planogram precision.

## Known limitations and mitigations

- SKU-110K’s single class cannot identify individual SKUs. OCR + product aliases and human override make this explicit.
- Dense products, reflection, occlusion and tiny labels can reduce recall/OCR quality. The pipeline exposes confidences and flags unresolved detections for review.
- A camera angle different from SKU-110K may create dataset shift. Test three angles/distances and retain example failures in the report.
- Alerts are based on confirmed matching and an explicit minimum-facing threshold, not raw low-confidence boxes.

## Out-of-scope uses

Do not use it for automatic purchasing, customer surveillance, employee performance scoring, price verification, or autonomous planogram penalties.

