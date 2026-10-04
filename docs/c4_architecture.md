# C4 architecture and data-flow evidence

This is a student-level C4 pack mapped to the actual implementation. It does
not claim cloud systems that have not been deployed.

## C1 — System context

```mermaid
C4Context
    title Retail Shelf Intelligence — system context
    Person(auditor, "Shelf auditor", "Captures a shelf photo and corrects uncertain results.")
    Person(manager, "Store manager", "Reviews restock reminders and compliance evidence.")
    System(system, "Retail Shelf Intelligence", "Confidence-aware detection, OCR-assisted planogram audit and review.")
    System_Ext(camera, "Phone / laptop camera", "Provides a shelf image.")
    System_Ext(dataset, "SKU-110K dataset", "Training and evaluation data for generic dense-product detection.")
    Rel(auditor, system, "Uploads, reviews and overrides", "Browser")
    Rel(manager, system, "Views evidence and alerts", "Browser")
    Rel(camera, system, "Captures image through browser", "getUserMedia")
    Rel(dataset, system, "Trains detector offline", "Ultralytics")
```

## C2 — Containers

```mermaid
C4Container
    title Retail Shelf Intelligence — container view
    Person(user, "Auditor / manager")
    System_Boundary(boundary, "Retail Shelf Intelligence") {
      Container(ui, "Browser dashboard", "HTML/CSS/JavaScript", "Capture/upload; planogram designer; review and alert actions.")
      Container(api, "API service", "FastAPI / Python", "Validation, detection orchestration, planogram logic, evidence and API.")
      ContainerDb(db, "Operational store", "MongoDB", "Products, planograms, audits, alerts and audit events.")
      Container(fs, "Evidence store", "Local filesystem", "Original image, annotated image, detection crops, JSON and HTML report.")
      Container(model, "Detection model", "YOLO11n checkpoint", "Finds generic product facings.")
      Container(ocr, "OCR engine", "EasyOCR", "Reads visible packaging text where possible.")
    }
    Rel(user, ui, "Uses")
    Rel(ui, api, "REST / JSON, multipart image")
    Rel(api, db, "Reads/writes", "Motor")
    Rel(api, fs, "Writes immutable per-audit artifacts")
    Rel(api, model, "Runs inference")
    Rel(api, ocr, "Reads crop text")
```

## C3 — API component view

```mermaid
flowchart LR
  U[Dashboard] --> R[FastAPI router]
  R --> V[Upload / request validation]
  R --> S[Security: API key + role]
  V --> I[YOLO + EasyOCR inference service]
  I --> A[Row clustering + catalogue resolution + planogram analysis]
  A --> L[Restock alert service]
  I --> E[Evidence bundle service]
  A --> M[(MongoDB)]
  L --> M
  E --> F[(Local evidence files)]
  R --> O[Structured logs, request IDs, latency metrics]
```

## Audit sequence and state

```mermaid
sequenceDiagram
    actor Auditor
    participant UI as Dashboard
    participant API as FastAPI
    participant AI as YOLO + OCR
    participant DB as MongoDB
    participant Files as Evidence folder
    Auditor->>UI: Capture or upload shelf image
    UI->>API: POST /api/v1/audits
    API->>API: Validate content type, size and decoded pixels
    API->>DB: Read product catalogue + active planogram
    API->>AI: Detect boxes and attempt OCR
    AI-->>API: boxes, confidences and OCR text
    API->>API: Cluster rows; count resolved SKUs; compare slots
    API->>Files: Save source, annotated image, crops, JSON, HTML report
    API->>DB: Save audit + audit_created event + alerts
    API-->>UI: Annotated image, results and review queue
    Auditor->>UI: Correct or remove uncertain detection
    UI->>API: POST /audits/{id}/overrides
    API->>DB: Save override event and recalculate analysis/alerts
```

## Deployment boundary

The prototype runs on one local machine through Docker Compose or the documented
virtual environment. MongoDB and the FastAPI service are separate containers in
`docker-compose.yml`; model weights and evidence folders are mounted volumes. A
later edge deployment can use the same FastAPI API with a local model volume. A
production deployment needs TLS, OAuth, a managed object store and a shared
rate limiter.
