"""Register an already completed Ultralytics run as reproducible MLflow evidence.

This is useful for the 20-epoch baseline that was trained before MLflow was added.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def numeric(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def mlflow_metric_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.\-/ ]", "", value).replace(" ", "_")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, help="Ultralytics train run directory")
    parser.add_argument("--tracking-uri", required=True, help="Example: sqlite:///C:/.../mlruns/mlflow.db")
    parser.add_argument("--run-name", default="baseline_imported")
    parser.add_argument("--notes", default="Imported after training; values are read from Ultralytics artifacts.")
    parser.add_argument(
        "--evaluation-json",
        default="",
        help="Optional test-evaluation JSON; its values are logged with a test_ prefix.",
    )
    args = parser.parse_args()

    import mlflow

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        raise SystemExit(f"Run directory not found: {run_dir}")
    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment("retail-shelf-intelligence")
    metrics: dict[str, float] = {}
    results_csv = run_dir / "results.csv"
    if results_csv.is_file():
        with results_csv.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        if rows:
            for key, value in rows[-1].items():
                parsed = numeric(value)
                if parsed is not None:
                    metrics[mlflow_metric_key(key.strip())] = parsed
    if args.evaluation_json:
        evaluation_path = Path(args.evaluation_json).resolve()
        if not evaluation_path.is_file():
            raise SystemExit(f"Evaluation JSON not found: {evaluation_path}")
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
        for key, value in evaluation.items():
            if isinstance(value, (int, float)):
                metrics[f"test_{mlflow_metric_key(key)}"] = float(value)
    with mlflow.start_run(run_name=args.run_name, tags={"project": "retail-shelf-intelligence", "imported": "true"}):
        mlflow.log_params({"source_run_dir": str(run_dir), "notes": args.notes})
        if metrics:
            mlflow.log_metrics(metrics)
        for artifact in [
            run_dir / "args.yaml",
            *run_dir.glob("*.csv"),
            *run_dir.glob("*.png"),
            run_dir / "weights" / "best.pt",
        ]:
            if artifact.is_file():
                mlflow.log_artifact(str(artifact))
        print(json.dumps({"tracked_run": args.run_name, "metrics_logged": len(metrics)}, indent=2))


if __name__ == "__main__":
    main()
