"""YOLOv8 / YOLOv11 Solid Waste Detection Training Pipeline.

Supports:
- Configurable base models (yolov8n.pt, yolov8s.pt, yolo11n.pt, etc.)
- CPU fallback and GPU acceleration
- CCTV-specific data augmentations
- Smoke-test mode vs Full production training
- Model artifact management (best.pt, checkpoints, metadata.json)
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

# Ensure project root is in sys.path for direct CLI script execution
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import torch
from ultralytics import YOLO

from ai.configs import get_solid_classes, CONFIGS_DIR
from ai.training.cctv_augmentations import get_cctv_augmentation_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("solid_train")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATASET_YAML = CONFIGS_DIR / "solid_dataset.yaml"
MODELS_SOLID_DIR = ROOT_DIR / "models" / "solid"
WEIGHTS_EXPORT_DIR = ROOT_DIR / "ai" / "models" / "weights"


def resolve_device(device_req: str) -> str:
    """Selects available compute device with CPU fallback."""
    if device_req.lower() == "auto":
        return "0" if torch.cuda.is_available() else "cpu"
    if "cuda" in device_req.lower() and not torch.cuda.is_available():
        logger.warning("CUDA requested but not available. Falling back to CPU.")
        return "cpu"
    return device_req


def train_solid_model(
    dataset_yaml: Path = DEFAULT_DATASET_YAML,
    base_model: str = "yolov8n.pt",
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
    """Executes YOLO detection training for solid waste classes."""
    selected_device = resolve_device(device)
    output_dir = project_dir or (MODELS_SOLID_DIR / "runs")
    output_dir.mkdir(parents=True, exist_ok=True)

    if smoke_test:
        logger.info("Executing in SMOKE-TEST mode (1 epoch, lightweight parameters)...")
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

    # Load YOLO model
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
        logger.info("Applying CCTV-specific data augmentations.")
        train_args.update(get_cctv_augmentation_config())

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

    # Copy to standardized model artifact location: models/solid/best.pt
    MODELS_SOLID_DIR.mkdir(parents=True, exist_ok=True)
    WEIGHTS_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    solid_best_dest = MODELS_SOLID_DIR / "best.pt"
    ai_weights_dest = WEIGHTS_EXPORT_DIR / "solid_waste_yolo.pt"

    if selected_weight.is_file():
        shutil.copy2(selected_weight, solid_best_dest)
        shutil.copy2(selected_weight, ai_weights_dest)
        logger.info("Saved best weight to: %s", solid_best_dest)
        logger.info("Exported to AI weights: %s", ai_weights_dest)

    # Extract metrics safely from results
    metrics_summary: Dict[str, Any] = {}
    try:
        if hasattr(results, "results_dict"):
            metrics_summary = {k: float(v) for k, v in results.results_dict.items()}
    except Exception:
        pass

    # Save metadata.json
    classes = get_solid_classes()
    metadata: Dict[str, Any] = {
        "model_name": f"SolidWasteYOLO_{base_model}",
        "architecture": base_model,
        "task": "detect",
        "domain": "solid_waste",
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
        "best_weight_path": str(solid_best_dest) if solid_best_dest.is_file() else None,
        "metrics": metrics_summary,
    }

    metadata_path = MODELS_SOLID_DIR / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Saved model metadata to: %s", metadata_path)

    return {
        "success": True,
        "experiment_name": experiment_name,
        "best_model_path": str(solid_best_dest),
        "metadata_path": str(metadata_path),
        "metrics": metrics_summary,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Train Solid Waste YOLO Detection Model")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATASET_YAML, help="Path to solid_dataset.yaml")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Base model weights")
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
    train_solid_model(
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
