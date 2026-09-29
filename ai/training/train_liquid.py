"""YOLOv8 / YOLOv11 Liquid Waste Instance Segmentation Training Pipeline.

Supports:
- Configurable segmentation base models (yolov8n-seg.pt, yolov8s-seg.pt, yolo11n-seg.pt, etc.)
- Automatic device resolution (GPU / CUDA with CPU fallback)
- CCTV-specific liquid data augmentations
- Smoke-test mode vs Full production training
- Model artifact management (models/liquid/best.pt, ai/models/weights/liquid_waste_yolo_seg.pt, metadata.json)
"""
import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import torch
from ultralytics import YOLO

from ai.configs import get_liquid_classes, CONFIGS_DIR
from ai.training.cctv_liquid_augmentations import get_liquid_cctv_augmentation_config
from ai.training.train_solid import resolve_device

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("liquid_train")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATASET_YAML = CONFIGS_DIR / "liquid_dataset.yaml"
MODELS_LIQUID_DIR = ROOT_DIR / "models" / "liquid"
WEIGHTS_EXPORT_DIR = ROOT_DIR / "ai" / "models" / "weights"


def train_liquid_model(
    dataset_yaml: Path = DEFAULT_DATASET_YAML,
    base_model: str = "yolov8n-seg.pt",
    epochs: int = 50,
    imgsz: int = 640,
    batch_size: int = 16,
    lr0: float = 0.01,
    lrf: float = 0.01,
    device: str = "auto",
    workers: int = 0,
    seed: int = 42,
    smoke_test: bool = False,
    use_cctv_augment: bool = True,
    project_dir: Optional[Path] = None,
    experiment_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Executes YOLO instance segmentation training for liquid waste classes."""
    selected_device = resolve_device(device)
    output_dir = project_dir or (MODELS_LIQUID_DIR / "runs")
    output_dir.mkdir(parents=True, exist_ok=True)

    if smoke_test:
        logger.info("Executing Liquid Pipeline in SMOKE-TEST mode (1 epoch, minimal resources)...")
        epochs = 1
        batch_size = min(batch_size, 4)
        experiment_name = experiment_name or "smoke_test"
    else:
        experiment_name = experiment_name or f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    logger.info("Base Model:    %s", base_model)
    logger.info("Dataset YAML:  %s", dataset_yaml)
    logger.info("Epochs:        %d", epochs)
    logger.info("Image Size:    %d", imgsz)
    logger.info("Batch Size:    %d", batch_size)
    logger.info("Device:        %s", selected_device)
    logger.info("Seed:          %d", seed)

    # Load YOLO segmentation model
    model = YOLO(base_model)

    train_args: Dict[str, Any] = {
        "data": str(dataset_yaml.resolve()),
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch_size,
        "device": selected_device,
        "workers": workers,
        "lr0": lr0,
        "lrf": lrf,
        "seed": seed,
        "project": str(output_dir.resolve()),
        "name": experiment_name,
        "exist_ok": True,
        "verbose": True,
    }

    if use_cctv_augment and not smoke_test:
        logger.info("Applying liquid CCTV-specific data augmentations.")
        train_args.update(get_liquid_cctv_augmentation_config())

    # Execute training
    start_time = datetime.now(timezone.utc)
    results = model.train(**train_args)
    end_time = datetime.now(timezone.utc)

    # Resolve run output paths
    run_dir = output_dir / experiment_name
    weights_dir = run_dir / "weights"
    best_weight = weights_dir / "best.pt"
    last_weight = weights_dir / "last.pt"
    selected_weight = best_weight if best_weight.is_file() else last_weight

    # Copy to models/liquid/best.pt and ai/models/weights/liquid_waste_yolo_seg.pt
    MODELS_LIQUID_DIR.mkdir(parents=True, exist_ok=True)
    WEIGHTS_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    liquid_best_dest = MODELS_LIQUID_DIR / "best.pt"
    ai_weights_dest = WEIGHTS_EXPORT_DIR / "liquid_waste_yolo_seg.pt"

    if selected_weight.is_file():
        shutil.copy2(selected_weight, liquid_best_dest)
        shutil.copy2(selected_weight, ai_weights_dest)
        logger.info("Saved best liquid weight to: %s", liquid_best_dest)
        logger.info("Exported to AI weights: %s", ai_weights_dest)

    # Extract metrics safely from results
    metrics_summary: Dict[str, Any] = {}
    try:
        if hasattr(results, "results_dict"):
            metrics_summary = {k: float(v) for k, v in results.results_dict.items()}
    except Exception:
        pass

    # Save metadata.json
    classes = get_liquid_classes()
    metadata: Dict[str, Any] = {
        "model_name": f"LiquidWasteYOLO_{base_model}",
        "architecture": base_model,
        "task": "segment",
        "domain": "liquid_waste",
        "training_date": start_time.isoformat(),
        "duration_seconds": (end_time - start_time).total_seconds(),
        "smoke_test": smoke_test,
        "epochs": epochs,
        "imgsz": imgsz,
        "batch_size": batch_size,
        "device": selected_device,
        "classes": {idx: name for idx, name in enumerate(classes)},
        "num_classes": len(classes),
        "dataset_yaml": str(dataset_yaml),
        "best_weight_path": str(liquid_best_dest) if liquid_best_dest.is_file() else None,
        "metrics": metrics_summary,
    }

    metadata_path = MODELS_LIQUID_DIR / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Saved model metadata to: %s", metadata_path)

    return {
        "success": True,
        "experiment_name": experiment_name,
        "best_model_path": str(liquid_best_dest),
        "metadata_path": str(metadata_path),
        "metrics": metrics_summary,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Train Liquid Waste YOLO Segmentation Model")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATASET_YAML, help="Path to liquid_dataset.yaml")
    parser.add_argument("--model", type=str, default="yolov8n-seg.pt", help="Base segmentation model weights")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--device", type=str, default="auto", help="Compute device (auto/cpu/cuda/0)")
    parser.add_argument("--workers", type=int, default=0, help="Dataloader workers (0 recommended on Windows)")
    parser.add_argument("--lr0", type=float, default=0.01, help="Initial learning rate")
    parser.add_argument("--lrf", type=float, default=0.01, help="Final learning rate factor")
    parser.add_argument("--smoke-test", action="store_true", help="Run 1-epoch smoke test")
    parser.add_argument("--no-cctv-augment", action="store_true", help="Disable CCTV augmentations")
    parser.add_argument("--project", type=Path, default=None, help="Output project directory")
    parser.add_argument("--name", type=str, default=None, help="Run name")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train_liquid_model(
        dataset_yaml=args.data,
        base_model=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch_size=args.batch,
        device=args.device,
        workers=args.workers,
        lr0=args.lr0,
        lrf=args.lrf,
        smoke_test=args.smoke_test,
        use_cctv_augment=not args.no_cctv_augment,
        project_dir=args.project,
        experiment_name=args.name,
    )
