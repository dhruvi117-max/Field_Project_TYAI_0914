# Technical verification record

Date: 4 October 2026  
Scope: final software verification; no additional model training was started.

## Completed checks

| Check | Result |
| --- | --- |
| Python unit tests | 8 passed |
| Python source compilation | Passed |
| Dashboard JavaScript syntax | Passed |
| API health check | MongoDB connected; trained model ready |
| MLflow baseline import | Completed; 20 saved validation metrics and run artifacts recorded locally |
| SKU-110K untouched test evaluation | Completed on 2,936 listed test images; one corrupt image skipped by Ultralytics |
| End-to-end local shelf audit | Completed and persisted in MongoDB |

## Detector test results

| Measure | Result |
| --- | ---: |
| Precision | 0.88669 |
| Recall | 0.81918 |
| mAP50 | 0.89131 |
| mAP50-95 | 0.53455 |
| Model inference time | 5.057 ms/image |
| Full detector validation time | 10.168 ms/image |

These are box-detection measurements for SKU-110K’s one generic product class.
They do not measure individual SKU identity, facing-count error, or planogram
precision.

## End-to-end audit check

The project submitted an existing local shelf image to the updated API on
4 October 2026:

| Field | Result |
| --- | --- |
| Audit ID | `92b37580-752c-421e-a560-c8bec41ca938` |
| Detected facings | 112 |
| Human review status | Required (expected because no confirmed SKU identity was available for most boxes) |
| Returned restock reminders | 2 |
| API inference time | 21,431 ms |
| Total API time | 21,646 ms |
| Evidence files | Source image, boxed image, 112 product crops, `summary.json`, `report.html` |

The report and crops are available in:

`data/audit_artifacts/92b37580-752c-421e-a560-c8bec41ca938/`

This confirms pipeline integration and artifact creation. It is not a
ground-truth operational-accuracy claim; staged-shelf tests with known facings
are still required for count-error, restock precision/recall, viewing-angle,
low-light, and OCR-failure evidence.
