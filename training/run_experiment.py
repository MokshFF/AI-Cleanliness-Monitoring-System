"""Training Runner & Experiment Tracker for Solid Waste Detection.

Conducts transfer-learning experiments, records detailed training logs,
saves best checkpoints, and tracks experiments in training/experiments/.
"""
import argparse
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import torch
from ultralytics import YOLO

from ai.configs import get_solid_classes, CONFIGS_DIR
from ai.training.cctv_augmentations import get_cctv_augmentation_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("experiment_runner")

EXPERIMENTS_DIR = _project_root / "training" / "experiments"
DEFAULT_DATASET_YAML = CONFIGS_DIR / "solid_dataset.yaml"
MODELS_SOLID_DIR = _project_root / "models" / "solid"
WEIGHTS_EXPORT_DIR = _project_root / "ai" / "models" / "weights"
ARCHIVE_DIR = WEIGHTS_EXPORT_DIR / "archive"


def run_experiment(
    model_name: str = "yolov8n.pt",
    dataset_yaml: Path = DEFAULT_DATASET_YAML,
    epochs: int = 15,
    imgsz: int = 416,
    batch_size: int = 16,
    patience: int = 10,
    lr0: float = 0.01,
    lrf: float = 0.01,
    seed: int = 42,
    device: str = "cpu",
    use_cctv_augment: bool = True,
    experiment_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs a full transfer learning experiment and logs to training/experiments/."""
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_id = experiment_id or f"exp_{Path(model_name).stem}_{timestamp}"
    exp_dir = EXPERIMENTS_DIR / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("STARTING EXPERIMENT: %s", exp_id)
    logger.info("Base Model:    %s", model_name)
    logger.info("Dataset:       %s", dataset_yaml)
    logger.info("Epochs:        %d", epochs)
    logger.info("Image Size:    %d", imgsz)
    logger.info("Batch Size:    %d", batch_size)
    logger.info("Device:        %s", device)
    logger.info("Augmentations: %s", "CCTV Augmentations" if use_cctv_augment else "Default")
    logger.info("=" * 70)

    aug_config = get_cctv_augmentation_config() if use_cctv_augment else {}

    model = YOLO(model_name)

    train_args: Dict[str, Any] = {
        "data": str(dataset_yaml.resolve()),
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch_size,
        "patience": patience,
        "device": device,
        "workers": 0,
        "lr0": lr0,
        "lrf": lrf,
        "seed": seed,
        "project": str(exp_dir.resolve()),
        "name": "run",
        "exist_ok": True,
        "verbose": True,
        "plots": True,
        "save": True,
    }
    if use_cctv_augment:
        train_args.update(aug_config)

    start_time = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    train_results = model.train(**train_args)

    t1 = time.perf_counter()
    end_time = datetime.now(timezone.utc)
    duration_sec = t1 - t0

    # Locate best weights
    run_dir = exp_dir / "run"
    best_weight = run_dir / "weights" / "best.pt"
    last_weight = run_dir / "weights" / "last.pt"
    selected_weight = best_weight if best_weight.is_file() else last_weight

    # Extract metrics
    results_dict = getattr(train_results, "results_dict", {})
    precision = float(results_dict.get("metrics/precision(B)", 0.0))
    recall = float(results_dict.get("metrics/recall(B)", 0.0))
    map50 = float(results_dict.get("metrics/mAP50(B)", 0.0))
    map50_95 = float(results_dict.get("metrics/mAP50-95(B)", 0.0))
    f1 = float(2 * (precision * recall) / (precision + recall + 1e-8))

    classes = get_solid_classes()

    experiment_record = {
        "experiment_id": exp_id,
        "model": model_name,
        "dataset": str(dataset_yaml),
        "classes": {idx: name for idx, name in enumerate(classes)},
        "epochs": epochs,
        "batch_size": batch_size,
        "image_size": imgsz,
        "optimizer": getattr(train_results, "optimizer", "auto"),
        "learning_rate": lr0,
        "lrf": lrf,
        "patience": patience,
        "augmentation_configuration": aug_config,
        "training_time_seconds": round(duration_sec, 2),
        "device": device,
        "gpu_available": torch.cuda.is_available(),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "best_weight_path": str(selected_weight),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "mAP50": round(map50, 4),
        "mAP50_95": round(map50_95, 4),
        "results_dict": {k: float(v) for k, v in results_dict.items()},
    }

    record_path = exp_dir / "experiment_metadata.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(experiment_record, f, indent=2)
    logger.info("Saved experiment metadata to: %s", record_path)

    # Save to models/solid/ and ai/models/weights/
    if selected_weight.is_file():
        MODELS_SOLID_DIR.mkdir(parents=True, exist_ok=True)
        solid_best_dest = MODELS_SOLID_DIR / "best.pt"
        shutil.copy2(selected_weight, solid_best_dest)

        ai_weights_dest = WEIGHTS_EXPORT_DIR / "solid_waste_yolo.pt"
        shutil.copy2(selected_weight, ai_weights_dest)
        logger.info("Exported weights to production: %s", ai_weights_dest)

        # Update metadata.json in models/solid/
        metadata_solid = dict(experiment_record)
        metadata_solid["production_weight"] = str(ai_weights_dest)
        with open(MODELS_SOLID_DIR / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata_solid, f, indent=2)

    logger.info("EXPERIMENT COMPLETE: mAP50=%.4f, mAP50-95=%.4f in %.1f s", map50, map50_95, duration_sec)
    return experiment_record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="yolov8n.pt")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--name", type=str, default=None)
    args = parser.parse_args()

    run_experiment(
        model_name=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch_size=args.batch,
        device=args.device,
        experiment_id=args.name,
    )
