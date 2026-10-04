# Threat model, test strategy and responsible-AI controls

## Threat model

| Threat / misuse | Impact | Implemented control | Verification |
| --- | --- | --- | --- |
| Fake, corrupt or oversized image | Resource exhaustion / crash | Extension, HTTP content-type, byte-size, Pillow decode and pixel dimension checks | Unit tests + manual 413/415 request. |
| Repeated expensive inference | GPU/CPU exhaustion | Per-client in-memory audit rate limit | Rapid-upload test returns HTTP 429. Replace with Redis/gateway for multi-instance use. |
| Path traversal in evidence URLs | Read unintended files | Audit IDs are server-generated UUIDs; static evidence root only | Try a malformed/foreign URL; server must not expose an arbitrary path. |
| Secret exposure | Unauthorized API access | `.env` ignored, optional constant-time API-key comparison, CI secret check | `git ls-files` contains no `.env`; API key set in local env only. |
| Low-confidence false SKU / restock claim | Incorrect retail action | Generic detection separated from OCR identity; conservative match threshold; review queue and override event | Blur/glare test must result in review, not invented SKU. |
| Alert fatigue | Alerts ignored | One active alert key per shelf/row/SKU; re-check resolves stale alerts | Repeat an audit and confirm no duplicated open alert. |
| Sensitive retail imagery | Privacy/store confidentiality issue | Permission checklist, no people/CCTV in committed samples, local evidence folders ignored | Review repository and demo images before release. |

## Responsible-AI boundary

The model detects generic product facings. SKU-110K is a one-class detection
dataset; it cannot by itself identify brands/SKUs. Packaging OCR is only a
proposal. The dashboard makes uncertain items explicitly reviewable, records
the reviewer and reason, and recalculates the planogram after the decision.
The system must not automatically order stock, penalise staff or perform
customer surveillance.

## Automated checks included

| Check | Location | Purpose |
| --- | --- | --- |
| Facing/alert logic | `backend/tests/test_audit_service.py` | Prevent false count and position logic regressions. |
| Decodable-image validation | `backend/tests/test_validation.py` | Reject non-image uploads before model inference. |
| Contract validation | `backend/tests/test_validation.py` | Reject empty planograms. |
| Compilation, tests and secret guard | `.github/workflows/ci.yml` | Repeatable pull-request checks. |

## Manual acceptance experiments still to record

| Experiment | Evidence to capture | Acceptance rule |
| --- | --- | --- |
| Normal staged shelf | Ground-truth facings vs dashboard count | Report count error and alert precision/recall. |
| 15° left/right viewpoint | Three photos and counts | State the degradation and a camera-placement rule. |
| Low light / glare | Photo + review result | Uncertain text is queued for review; no invented SKU. |
| Missing product | Planogram, photo and resulting alert | Below-minimum SKU gets one restock reminder. |
| Misplaced confirmed product | Screenshot of wrong row/position | Mismatch is visible as unexpected product or position deviation. |
| Security test | API responses / logs | Wrong type 415, oversize 413, excessive uploads 429, configured key 401. |

Keep raw results, screenshots and timestamped test sheets in the final
evaluation dossier; do not fill values before performing each test.
