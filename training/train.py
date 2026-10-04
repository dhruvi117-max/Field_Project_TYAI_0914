"""Fine-tune a pretrained YOLO model for dense shelf-product detection.

Example:
    python training/train.py --data SKU-110K.yaml --model yolo11s.pt --epochs 150 --imgsz 1280
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train YOLO on SKU-110K")
    parser.add_argument("--data", default="SKU-110K.yaml", help="Ultralytics dataset YAML or local YAML")
    parser.add_argument("--model", default="yolo11s.pt", help="Pretrained YOLO checkpoint")
    parser.add_argument("--epochs", default=150, type=int, help="Upper limit; early stopping remains enabled")
    parser.add_argument("--imgsz", default=1280, type=int, help="Large image size helps with small, dense products")
    parser.add_argument("--batch", default=-1, type=int, help="-1 automatically fits batch size to GPU memory")
    parser.add_argument("--device", default=None, help="CUDA device, e.g. 0. Omit for auto selection")
    parser.add_argument("--name", default="sku110k_yolo11s_150e")
    parser.add_argument(
        "--mlflow-uri",
        default=os.environ.get("MLFLOW_TRACKING_URI", ""),
        help="Optional MLflow tracking URI, e.g. sqlite:///C:/path/to/mlruns/mlflow.db",
    )
    return parser.parse_args()


def mlflow_metric_key(value: str) -> str:
    """Convert Ultralytics names such as metrics/mAP50(B) to MLflow-safe names."""
    return re.sub(r"[^0-9A-Za-z_.\-/ ]", "", value).replace(" ", "_")


def main() -> None:
    args = parse_args()
    try:
        from ultralytics import YOLO
    except ImportError as error:
        raise SystemExit("Install backend requirements before training: pip install -r backend/requirements.txt") from error

    mlflow = None
    mlflow_run = None
    if args.mlflow_uri:
        try:
            import mlflow as mlflow_module

            mlflow = mlflow_module
            mlflow.set_tracking_uri(args.mlflow_uri)
            mlflow.set_experiment("retail-shelf-intelligence")
            mlflow_run = mlflow.start_run(
                run_name=args.name,
                tags={
                    "project": "retail-shelf-intelligence",
                    "dataset": str(args.data),
                    "model_family": "YOLO",
                    "purpose": "SKU-110K dense product detection",
                },
                log_system_metrics=True,
            )
            mlflow.log_params({
                "base_model": args.model, "data": args.data, "epochs_requested": args.epochs,
                "imgsz": args.imgsz, "batch": args.batch, "device": args.device or "auto",
                "seed": 42, "deterministic": True, "patience": 30,
            })
            print(f"MLflow tracking enabled: {mlflow.get_tracking_uri()}")
        except Exception as error:
            # Tracking must not discard an expensive training run because a local tracker is unavailable.
            print(f"Warning: MLflow tracking was not started: {error}")
            mlflow = None

    model = YOLO(args.model)
    try:
        model.train(
            data=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            project="runs/train",
            name=args.name,
            exist_ok=True,
            patience=30,
            optimizer="auto",
            cache="disk",
            workers=4,
            seed=42,
            deterministic=True,
            close_mosaic=10,
            plots=True,
            verbose=True,
        )
    except Exception:
        if mlflow_run:
            mlflow.end_run(status="FAILED")
        raise
    # Ultralytics determines the final run directory (and may add a task subfolder).
    # Reading it from the trainer avoids assuming a platform/version-specific path.
    run_dir = Path(model.trainer.save_dir)
    best_weights = run_dir / "weights" / "best.pt"
    if not best_weights.is_file():
        raise RuntimeError(f"Training ended without expected best weights at {best_weights}")
    # Test the best validation checkpoint, not the final epoch checkpoint.
    metrics = YOLO(str(best_weights)).val(data=args.data, split="test", imgsz=args.imgsz, device=args.device, plots=True)
    summary = {
        "model": args.model,
        "data": args.data,
        "epochs_requested": args.epochs,
        "imgsz": args.imgsz,
        "seed": 42,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "best_weights": str(best_weights),
        "metrics": {key: float(value) for key, value in metrics.results_dict.items() if isinstance(value, (int, float))},
    }
    (run_dir / "experiment_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if mlflow_run:
        try:
            mlflow.log_metrics({mlflow_metric_key(key): value for key, value in summary["metrics"].items()})
            mlflow.log_artifact(str(run_dir / "experiment_summary.json"))
            for artifact in (run_dir / "results.csv", run_dir / "results.png", best_weights):
                if artifact.is_file():
                    mlflow.log_artifact(str(artifact))
            mlflow.end_run(status="FINISHED")
        except Exception as error:
            print(f"Warning: training completed but MLflow finalisation failed: {error}")
    print(json.dumps(summary, indent=2))
    print("\nCopy the best model to models/shelf_yolo.pt to enable backend inference.")


if __name__ == "__main__":
    main()
