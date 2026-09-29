"""Reproducible dataset splitting utility for Solid Waste YOLO annotations.

Splits raw or annotated images/labels into train/val/test partitions.
Features:
- Configurable split ratios (default 70% train, 20% val, 10% test)
- Deterministic random seed
- Data-leakage avoidance (SHA-256 hash deduplication/grouping)
- Generates split manifest and audit log in metadata directory
"""
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any

# Ensure project root is in sys.path for direct CLI script execution
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

class DatasetSplitter:
    """Partitions raw paired images and labels into train, val, and test splits."""

    def __init__(
        self,
        dataset_root: Path,
        train_ratio: float = 0.70,
        val_ratio: float = 0.20,
        test_ratio: float = 0.10,
        seed: int = 42,
    ) -> None:
        self.dataset_root = Path(dataset_root)
        total_ratio = train_ratio + val_ratio + test_ratio
        if not (0.999 <= total_ratio <= 1.001):
            raise ValueError(f"Ratios must sum to 1.0, got {total_ratio:.4f}")

        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.seed = seed

    def compute_file_hash(self, file_path: Path) -> str:
        """Computes SHA-256 hash of a file for duplicate detection."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def discover_pairs(
        self, source_images_dir: Path, source_labels_dir: Path
    ) -> List[Tuple[Path, Optional[Path], str]]:
        """Discovers matching image and label pairs, computing content hashes to prevent leakage.
        
        Returns:
            List of (image_path, label_path, hash_digest)
        """
        image_files = [
            p for p in source_images_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        ]

        pairs: List[Tuple[Path, Optional[Path], str]] = []
        for img_path in sorted(image_files):
            lbl_path = source_labels_dir / f"{img_path.stem}.txt"
            matched_lbl = lbl_path if lbl_path.is_file() else None
            h = self.compute_file_hash(img_path)
            pairs.append((img_path, matched_lbl, h))

        return pairs

    def split_dataset(
        self,
        source_images_dir: Path,
        source_labels_dir: Path,
        copy_files: bool = True,
    ) -> Dict[str, Any]:
        """Performs deterministic split and organizes files into destination partitions."""
        pairs = self.discover_pairs(source_images_dir, source_labels_dir)
        if not pairs:
            return {
                "success": False,
                "message": "No valid source image-label pairs found.",
                "total_samples": 0,
            }

        # Deduplication & Leakage avoidance: group identical images by hash
        hash_to_pairs: Dict[str, List[Tuple[Path, Optional[Path]]]] = {}
        for img_p, lbl_p, h in pairs:
            if h not in hash_to_pairs:
                hash_to_pairs[h] = []
            hash_to_pairs[h].append((img_p, lbl_p))

        unique_hashes = sorted(list(hash_to_pairs.keys()))
        rng = random.Random(self.seed)
        rng.shuffle(unique_hashes)

        total_unique = len(unique_hashes)
        n_train = int(round(total_unique * self.train_ratio))
        n_val = int(round(total_unique * self.val_ratio))
        # remainder to test to ensure exact conservation
        n_test = total_unique - n_train - n_val

        train_hashes = unique_hashes[:n_train]
        val_hashes = unique_hashes[n_train : n_train + n_val]
        test_hashes = unique_hashes[n_train + n_val :]

        split_assignments: Dict[str, List[Tuple[Path, Optional[Path]]]] = {
            "train": [pair for h in train_hashes for pair in hash_to_pairs[h]],
            "val": [pair for h in val_hashes for pair in hash_to_pairs[h]],
            "test": [pair for h in test_hashes for pair in hash_to_pairs[h]],
        }

        # Prepare target directories
        manifest: Dict[str, Any] = {
            "seed": self.seed,
            "train_ratio": self.train_ratio,
            "val_ratio": self.val_ratio,
            "test_ratio": self.test_ratio,
            "total_samples": len(pairs),
            "unique_hashes": total_unique,
            "duplicate_count": len(pairs) - total_unique,
            "splits": {"train": [], "val": [], "test": []},
        }

        for split_name, assigned_pairs in split_assignments.items():
            dest_img_dir = self.dataset_root / "images" / split_name
            dest_lbl_dir = self.dataset_root / "labels" / split_name
            dest_img_dir.mkdir(parents=True, exist_ok=True)
            dest_lbl_dir.mkdir(parents=True, exist_ok=True)

            for img_p, lbl_p in assigned_pairs:
                manifest["splits"][split_name].append({
                    "image": img_p.name,
                    "label": lbl_p.name if lbl_p else None,
                })
                if copy_files:
                    shutil.copy2(img_p, dest_img_dir / img_p.name)
                    if lbl_p:
                        shutil.copy2(lbl_p, dest_lbl_dir / lbl_p.name)

        # Write manifest
        meta_dir = self.dataset_root / "metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = meta_dir / "split_manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return {
            "success": True,
            "total_samples": len(pairs),
            "train_count": len(split_assignments["train"]),
            "val_count": len(split_assignments["val"]),
            "test_count": len(split_assignments["test"]),
            "manifest_path": str(manifest_file),
        }
