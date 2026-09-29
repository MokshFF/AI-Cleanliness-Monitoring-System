"""AI module for Solid and Liquid waste detection, segmentation, and temporal validation."""
from pathlib import Path

AI_DIR = Path(__file__).resolve().parent
CONFIGS_DIR = AI_DIR / "configs"
MODELS_DIR = AI_DIR / "models"
WEIGHTS_DIR = MODELS_DIR / "weights"
DATASETS_DIR = AI_DIR / "datasets"

__all__ = ["AI_DIR", "CONFIGS_DIR", "MODELS_DIR", "WEIGHTS_DIR", "DATASETS_DIR"]
