# Operations, MLflow and clean-machine runbook

## Operational evidence

Every API response carries `X-Request-ID`. The backend writes structured event
logs for request completion, audit completion and human overrides. It records
mean request, inference and total-audit latency in the local Prometheus-style
endpoint:

```text
GET /api/v1/metrics
GET /api/v1/health
```

Do not expose `/metrics` publicly in a real deployment. For the class demo,
open it locally and capture a screenshot after several audits.

## Evidence produced per audit

`data/audit_artifacts/<audit-id>/` contains:

- Original uploaded shelf image
- `annotated.jpg` with the real detection boxes
- `crops/` for individual detections
- `summary.json` of the API decision
- `report.html` printable evidence report

The MongoDB audit document remains the authoritative record; the folder makes
the decision easy to demonstrate and inspect.

## MLflow experiment tracking

MLflow is configured as an optional local tracker. Install the updated
requirements once:

```bat
cd /d "C:\\Users\\dhruv\\Desktop\\ffpp"
.venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt
```

For the next training run, log parameters, metrics, selected artifacts and
system metrics:

```bat
set MLFLOW_TRACKING_URI=sqlite:///C:/Users/dhruv/Desktop/ffpp/mlruns/mlflow.db
.venv\\Scripts\\python.exe training\\train.py --data SKU-110K.yaml --model yolo11n.pt --epochs 30 --imgsz 640 --batch 2 --device 0 --name baseline_yolo11n
```

To register the already completed 20-epoch run without retraining:

```bat
.venv\\Scripts\\python.exe training\\log_existing_run.py --run-dir runs\\detect\\runs\\train\\baseline_rtx3050 --tracking-uri sqlite:///C:/Users/dhruv/Desktop/ffpp/mlruns/mlflow.db --run-name baseline_rtx3050_20e
```

MLflow’s tracker URI, parameter/metric logging and run lifecycle follow the
[official MLflow Tracking API](https://www.mlflow.org/docs/latest/ml/tracking/tracking-api).
It is evidence tracking, not a claim that the model has improved.

## Clean-machine reproducibility check

1. Clone/copy the repository without `.venv`, `data/uploads`, `data/audit_artifacts`, `mlruns`, model weights or `.env`.
2. Copy `backend/.env.example` to `backend/.env`; set only local values.
3. Install `backend/requirements.txt`.
4. Start MongoDB with Docker Compose, or start a local MongoDB service.
5. Copy a permission-cleared checkpoint to `models/shelf_yolo.pt`.
6. Run `python -m uvicorn app.main:app --reload` from `backend`.
7. Create a product and planogram in the dashboard; submit a staged-shelf image.
8. Run `python -m pytest tests -q` from `backend`.

The CI workflow repeats source compilation, unit tests and basic secret checks
on each GitHub push/pull request. It cannot run an inference acceptance test
because trained weights and large data are deliberately excluded from Git.
