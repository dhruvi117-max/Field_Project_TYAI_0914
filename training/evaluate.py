"""Evaluate a trained checkpoint on the untouched SKU-110K test split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", default="models/shelf_yolo.pt")
    parser.add_argument("--data", default="SKU-110K.yaml")
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()
    from ultralytics import YOLO

    model = YOLO(args.weights)
    result = model.val(data=args.data, split="test", imgsz=args.imgsz, device=args.device, plots=True)
    output = {key: float(value) for key, value in result.results_dict.items() if isinstance(value, (int, float))}
    # Ultralytics reports milliseconds per image for preprocess/inference/postprocess.
    output["latency_ms_per_image"] = round(sum(float(value) for value in result.speed.values()), 3)
    output["inference_ms_per_image"] = round(float(result.speed.get("inference", 0.0)), 3)
    print(json.dumps(output, indent=2))
    Path("runs/evaluation_metrics.json").parent.mkdir(parents=True, exist_ok=True)
    Path("runs/evaluation_metrics.json").write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
