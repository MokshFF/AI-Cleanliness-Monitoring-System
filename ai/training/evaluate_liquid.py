"""Evaluation pipeline for Liquid Waste YOLO Segmentation models.

Computes and reports real evaluation metrics:
- Mask Precision, Recall, mAP@0.50, mAP@0.50:0.95
- Box Precision, Recall, mAP@0.50, mAP@0.50:0.95
- Class-wise breakdown for all 4 liquid waste classes
- Exports evaluation_report.json
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import torch
from ultralytics import YOLO

from ai.configs import get_liquid_classes, CONFIGS_DIR
from ai.training.train_solid import resolve_device

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("liquid_evaluate")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATASET_YAML = CONFIGS_DIR / "liquid_dataset.yaml"
DEFAULT_MODEL_PATH = ROOT_DIR / "models" / "liquid" / "best.pt"


def evaluate_liquid_model(
    model_path: Path = DEFAULT_MODEL_PATH,
    dataset_yaml: Path = DEFAULT_DATASET_YAML,
    split: str = "val",
    imgsz: int = 640,
    batch_size: int = 16,
    device: str = "auto",
    project_dir: Optional[Path] = None,
    name: str = "eval",
) -> Dict[str, Any]:
    """Runs Ultralytics validation on the specified segmentation model and dataset split."""
    if not model_path.is_file():
        raise FileNotFoundError(f"Model weights not found at: {model_path}")
    if not dataset_yaml.is_file():
        raise FileNotFoundError(f"Dataset configuration not found at: {dataset_yaml}")

    selected_device = resolve_device(device)

    logger.info("Evaluating liquid model: %s", model_path)
    logger.info("Dataset YAML:           %s", dataset_yaml)
    logger.info("Split:                  %s", split)
    logger.info("Device:                 %s", selected_device)

    model = YOLO(str(model_path))

    save_dir = project_dir or (ROOT_DIR / "models" / "liquid" / "evaluation")
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

    classes = get_liquid_classes()

    # Extract mask metrics if available (Segmentation task)
    mask_metrics_summary: Dict[str, Any] = {}
    box_metrics_summary: Dict[str, Any] = {}
    per_class_metrics: Dict[str, Dict[str, Any]] = {}

    if hasattr(metrics, "seg") and metrics.seg is not None:
        seg_m = metrics.seg
        mask_mp = float(seg_m.mp)
        mask_mr = float(seg_m.mr)
        mask_map50 = float(seg_m.map50)
        mask_map = float(seg_m.map)
        mask_f1 = float(2 * (mask_mp * mask_mr) / (mask_mp + mask_mr + 1e-8))

        mask_metrics_summary = {
            "precision": round(mask_mp, 4),
            "recall": round(mask_mr, 4),
            "f1": round(mask_f1, 4),
            "map50": round(mask_map50, 4),
            "map50_95": round(mask_map, 4),
        }

        for idx, class_name in enumerate(classes):
            if idx < len(seg_m.p):
                p_v = float(seg_m.p[idx])
                r_v = float(seg_m.r[idx])
                ap50 = float(seg_m.ap50[idx]) if idx < len(seg_m.ap50) else 0.0
                ap = float(seg_m.ap[idx]) if idx < len(seg_m.ap) else 0.0
                per_class_metrics[class_name] = {
                    "mask_precision": round(p_v, 4),
                    "mask_recall": round(r_v, 4),
                    "mask_map50": round(ap50, 4),
                    "mask_map50_95": round(ap, 4),
                }

    if hasattr(metrics, "box") and metrics.box is not None:
        box_m = metrics.box
        box_mp = float(box_m.mp)
        box_mr = float(box_m.mr)
        box_map50 = float(box_m.map50)
        box_map = float(box_m.map)
        box_metrics_summary = {
            "precision": round(box_mp, 4),
            "recall": round(box_mr, 4),
            "map50": round(box_map50, 4),
            "map50_95": round(box_map, 4),
        }

    results: Dict[str, Any] = {
        "model_path": str(model_path),
        "split": split,
        "task": "segment",
        "mask_metrics": mask_metrics_summary,
        "box_metrics": box_metrics_summary,
        "per_class": per_class_metrics,
        "plots_directory": str(metrics.save_dir),
    }

    # Save summary report
    report_file = Path(metrics.save_dir) / "evaluation_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info("=" * 60)
    logger.info("LIQUID EVALUATION SUMMARY (%s split)", split.upper())
    logger.info("Mask Precision: %.4f", mask_metrics_summary.get("precision", 0.0))
    logger.info("Mask Recall:    %.4f", mask_metrics_summary.get("recall", 0.0))
    logger.info("Mask mAP@0.50:  %.4f", mask_metrics_summary.get("map50", 0.0))
    logger.info("Mask mAP@0.5-95:%.4f", mask_metrics_summary.get("map50_95", 0.0))
    logger.info("=" * 60)
    logger.info("Full evaluation report saved to: %s", report_file)

    return results


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate Liquid Waste YOLO Segmentation Model")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH, help="Path to best.pt")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATASET_YAML, help="Path to liquid_dataset.yaml")
    parser.add_argument("--split", type=str, default="val", choices=["train", "val", "test"])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", type=str, default="auto")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluate_liquid_model(
        model_path=args.model,
        dataset_yaml=args.data,
        split=args.split,
        imgsz=args.imgsz,
        batch_size=args.batch,
        device=args.device,
    )
