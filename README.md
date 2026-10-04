# Retail Shelf Intelligence

A college AI project that checks a shelf photo.

It finds product facings, tries to read packaging text, compares the result
with a planogram, creates a restock reminder when stock is low, and lets a
human correct uncertain AI results.

## What the system does

1. Upload or capture a shelf photo.
2. YOLO finds individual product facings and draws boxes around them.
3. OCR tries to read visible packaging text.
4. The system compares confirmed products and facing counts with the saved
   planogram.
5. It flags missing, misplaced, low-stock, or uncertain items.
6. The auditor can correct or remove an uncertain detection.
7. It saves the audit, alerts, audit events, source photo, boxed image,
   product crops, JSON data, and a printable report.

## Important limitation

SKU-110K teaches YOLO to find **generic product boxes**. It does not teach the
model the name of every product. A product identity is only suggested by OCR
plus the product catalogue. If that is uncertain, the dashboard asks a human
to review it instead of guessing.

## Start the project

These commands are for **Command Prompt**.

First make sure MongoDB is running. You can use either your installed MongoDB
service or Docker Desktop. Then run:

```bat
cd /d "C:\Users\dhruv\Desktop\ffpp\backend"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open:

- Dashboard: http://127.0.0.1:8000
- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/api/v1/health
- Local metrics: http://127.0.0.1:8000/api/v1/metrics

If `backend\.env` does not exist, create it once:

```bat
cd /d "C:\Users\dhruv\Desktop\ffpp"
copy backend\.env.example backend\.env
```

## How to use the dashboard

### 1. Create the planogram

Open **Planogram, alerts and human review workspace**.

1. Enter a SKU, product name, and words OCR may read from the pack.
2. Select **Add catalogue product**.
3. Choose shelf row, product SKU, expected facings, and minimum facings.
4. Select **Add slot** for every product requirement.
5. Select **Save planogram**.

Example:

| Field | Example |
| --- | --- |
| SKU | `COLA-500` |
| Shelf row | `1` |
| Expected facings | `4` |
| Minimum before restock | `2` |
| Position | `left` |

“Expected” is the ideal count. “Minimum” is the count below which the system
creates a restock reminder.

### 2. Audit a shelf

1. Use **Upload shelf photo** or **Capture live photo**.
2. Check the store, shelf, and auditor details.
3. Select **Analyse shelf**.
4. View the real detection boxes on the returned image.
5. Open the management workspace to see alerts, audit history, and review.

### 3. Review uncertain results

The **Human review queue** shows items whose product identity is uncertain.

- Choose the correct SKU and select **Apply SKU**, or
- Select **Remove** if the box is not a valid product facing.

The planogram and restock reminders are recalculated after every human
decision. The decision is saved in the audit trail.

### 4. Open audit evidence

Use **Recent audit evidence** and select **Open** or **Report**.

For every new audit, the project saves:

- original shelf photo
- boxed/annotated result image
- crop for each detection
- JSON audit summary
- printable HTML evidence report

The files are in `data\audit_artifacts\<audit-id>\`.

## Current model result

The installed model is a **YOLO11n, 20-epoch SKU-110K baseline** evaluated at
640 px on the NVIDIA RTX 3050 Laptop GPU.

| Test measurement | Result |
| --- | ---: |
| mAP50 | 0.8913 |
| mAP50–95 | 0.5346 |
| Precision | 0.8867 |
| Recall | 0.8192 |
| Model inference | 5.057 ms per image |

These are genuine generic-product detection metrics from the 2,936-image
untouched SKU-110K test split. One corrupt dataset image was skipped by
Ultralytics. They are not SKU-identification or planogram-accuracy metrics.

No more training is required to run the current prototype.

## Test the backend

```bat
cd /d "C:\Users\dhruv\Desktop\ffpp\backend"
..\.venv\Scripts\python.exe -m pytest tests -q
```

## Key folders

| Folder/file | Purpose |
| --- | --- |
| `backend\app` | FastAPI API, MongoDB, planogram, alerts, OCR, review and evidence code |
| `Retail Shelf Intelligence — Visual Analytics Report.html` | Dashboard |
| `models\shelf_yolo.pt` | Current trained baseline model |
| `data\uploads` | Uploaded shelf images |
| `data\audit_artifacts` | Per-audit reports and detection crops |
| `training` | Training, evaluation and MLflow tracking scripts |
| `docs` | Architecture, model card, evaluation, data governance, security and operations evidence |

## Project evidence documents

- [Architecture / C4 diagrams](docs/c4_architecture.md)
- [Solution design and API contracts](docs/solution_design.md)
- [Model card](docs/model_card.md)
- [Evaluation plan](docs/evaluation_plan.md)
- [Data governance and provenance](docs/data_governance.md)
- [Threat model and test strategy](docs/security_test_strategy.md)
- [Operations and MLflow guide](docs/operations_mlops.md)
- [Technical verification record](docs/verification_record.md)

## Before final submission

The software is ready for the live prototype. Still collect these real-world
evidence items before submission:

- Screenshots/results for a normal shelf, low light, angled shelf, missing
  product, misplaced product, and unreadable label.
- Your actual product catalogue and a permission-cleared reference planogram.
- A screenshot of GitHub Actions passing after you publish the repository.
- Demo video, final report, slides, and each student’s contribution evidence.

Do not upload `.env`, the 38 GB dataset, model weights, database dumps, or
private shelf images to GitHub.
"# Field_Project_TYAI_0914" 
