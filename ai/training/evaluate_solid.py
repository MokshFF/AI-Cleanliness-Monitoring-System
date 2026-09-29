"""Evaluation pipeline for Solid Waste YOLO Detection models.

Computes and reports real evaluation metrics:
- Overall & Per-class Precision
- Overall & Per-class Recall
- mAP@0.50 and mAP@0.50:0.95
- F1-Score
- Confusion matrix and PR curves export
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root is in sys.path for direct CLI script execution
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import torch
from ultralytics import YOLO

from ai.configs import get_solid_classes, CONFIGS_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("solid_evaluate")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATASET_YAML = CONFIGS_DIR / "solid_dataset.yaml"
DEFAULT_MODEL_PATH = ROOT_DIR / "models" / "solid" / "best.pt"


def evaluate_solid_model(
    model_path: Path = DEFAULT_MODEL_PATH,
    dataset_yaml: Path = DEFAULT_DATASET_YAML,
    split: str = "val",
    imgsz: int = 640,
    batch_size: int = 16,
    device: str = "auto",
    project_dir: Optional[Path] = None,
    name: str = "eval",
) -> Dict[str, Any]:
    """Runs Ultralytics validation on the specified model and dataset split."""
    if not model_path.is_file():
        raise FileNotFoundError(f"Model weights not found at: {model_path}")
    if not dataset_yaml.is_file():
        raise FileNotFoundError(f"Dataset configuration not found at: {dataset_yaml}")

    from ai.training.train_solid import resolve_device
    selected_device = resolve_device(device)

    logger.info("Evaluating model: %s", model_path)
    logger.info("Dataset YAML:     %s", dataset_yaml)
    logger.info("Split:            %s", split)
    logger.info("Device:           %s", selected_device)

    model = YOLO(str(model_path))

    save_dir = project_dir or (ROOT_DIR / "models" / "solid" / "evaluation")
    save_dir.mkdir(parents=True, exist_ok=True)

    metrics = model.val(
        data=str(dataset_yaml.resolve()),
        split=split,
        imgsz=imgsz,
        batch=batch_size,
        device=selected_device,
        project=str(save_dir.resolve()),
        name=name,
        plots=True,
        save_json=True,
        verbose=True,
    )

    classes = get_solid_classes()
    box_metrics = metrics.box

    # Extract overall metrics
    precision = float(box_metrics.mp)
    recall = float(box_metrics.mr)
    map50 = float(box_metrics.map50)
    map50_95 = float(box_metrics.map)
    f1 = float(2 * (precision * recall) / (precision + recall + 1e-8))

    # Extract per-class metrics
    per_class_metrics: Dict[str, Dict[str, float]] = {}
    class_map = metrics.names

    for idx, class_name in enumerate(classes):
        if idx < len(box_metrics.p):
            p_val = float(box_metrics.p[idx])
            r_val = float(box_metrics.r[idx])
            ap50 = float(box_metrics.ap50[idx]) if idx < len(box_metrics.ap50) else 0.0
            ap = float(box_metrics.ap[idx]) if idx < len(box_metrics.ap) else 0.0
            class_f1 = float(2 * (p_val * r_val) / (p_val + r_val + 1e-8))
            per_class_metrics[class_name] = {
                "precision": round(p_val, 4),
                "recall": round(r_val, 4),
                "f1": round(class_f1, 4),
                "map50": round(ap50, 4),
                "map50_95": round(ap, 4),
            }
        else:
            per_class_metrics[class_name] = {
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "map50": 0.0,
                "map50_95": 0.0,
            }

    results: Dict[str, Any] = {
        "model_path": str(model_path),
        "split": split,
        "overall": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "map50": round(map50, 4),
            "map50_95": round(map50_95, 4),
        },
        "per_class": per_class_metrics,
        "plots_directory": str(metrics.save_dir),
    }

    # Save summary report
    report_file = Path(metrics.save_dir) / "evaluation_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info("=" * 60)
    logger.info("EVALUATION SUMMARY (%s split)", split.upper())
    logger.info("Precision:  %.4f", precision)
    logger.info("Recall:     %.4f", recall)
    logger.info("F1-Score:   %.4f", f1)
    logger.info("mAP@0.50:   %.4f", map50)
    logger.info("mAP@0.5-95: %.4f", map50_95)
    logger.info("=" * 60)
    logger.info("Full report saved to: %s", report_file)

    return results


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate Solid Waste YOLO Detection Model")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH, help="Path to best.pt")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATASET_YAML, help="Path to solid_dataset.yaml")
    parser.add_argument("--split", type=str, default="val", choices=["train", "val", "test"])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", type=str, default="auto")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluate_solid_model(
        model_path=args.model,
        dataset_yaml=args.data,
        split=args.split,
        imgsz=args.imgsz,
        batch_size=args.batch,
        device=args.device,
    )
