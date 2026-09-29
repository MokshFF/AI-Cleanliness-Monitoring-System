"""Class loading utilities and schema definitions for AI waste models."""
from pathlib import Path
from typing import Dict, List, Any
import yaml

CONFIGS_DIR = Path(__file__).resolve().parent

def load_yaml(file_path: Path) -> Dict[str, Any]:
    """Safely loads a YAML configuration file."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Configuration file not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_solid_classes() -> List[str]:
    """Returns the ordered list of solid waste classes."""
    data = load_yaml(CONFIGS_DIR / "solid_classes.yaml")
    return list(data.get("class_names", []))

def get_liquid_classes() -> List[str]:
    """Returns the ordered list of liquid waste classes."""
    data = load_yaml(CONFIGS_DIR / "liquid_classes.yaml")
    return list(data.get("class_names", []))

__all__ = ["load_yaml", "get_solid_classes", "get_liquid_classes"]
