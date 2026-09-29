"""Liquid Waste Dataset Validation Utility.

Validates YOLO instance segmentation dataset annotations against the cleanliness liquid taxonomy:
- Missing images or labels
- Malformed segmentation polygon annotations (token counts, vertex counts)
- Class IDs strictly within [0..3]
- Polygon coordinate bounds [0.0, 1.0]
- Insufficient vertices (< 3 vertices / 6 coordinates)
- Degenerate / zero-area polygons
- Empty annotation files
- Corrupted or unreadable image bytes
- Duplicate image files (SHA-256 hash matching)
"""
import hashlib
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PIL import Image
import cv2
import numpy as np
from ai.configs import get_liquid_classes

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

class LiquidDatasetValidator:
    """Validates YOLO segmentation formatted dataset against liquid waste taxonomy."""

    def __init__(self, dataset_root: Path, class_names: Optional[List[str]] = None) -> None:
        self.dataset_root = Path(dataset_root)
        self.class_names = class_names or get_liquid_classes()
        self.valid_class_ids = set(range(len(self.class_names)))

    def validate_segmentation_file(
        self, label_path: Path
    ) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
        """Parses and validates a single YOLO segmentation label file.
        
        Returns:
            (is_valid, parsed_polygons, error_messages)
        """
        polygons: List[Dict[str, Any]] = []
        errors: List[str] = []

        try:
            content = label_path.read_text(encoding="utf-8").strip()
        except Exception as e:
            return False, [], [f"Failed to read label file {label_path.name}: {e}"]

        if not content:
            return True, [], [f"Empty annotation file: {label_path.name}"]

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        for line_num, line in enumerate(lines, start=1):
            tokens = line.split()

            # Class ID + 2*N coordinates => tokens count must be >= 7 and odd
            if len(tokens) < 7:
                errors.append(
                    f"{label_path.name}:line {line_num}: insufficient tokens for polygon (got {len(tokens)}, min 7)"
                )
                continue

            if (len(tokens) - 1) % 2 != 0:
                errors.append(
                    f"{label_path.name}:line {line_num}: uneven coordinate count ({len(tokens) - 1} values)"
                )
                continue

            try:
                class_id = int(tokens[0])
            except ValueError:
                errors.append(f"{label_path.name}:line {line_num}: class_id '{tokens[0]}' is not an integer")
                continue

            if class_id not in self.valid_class_ids:
                errors.append(
                    f"{label_path.name}:line {line_num}: invalid class_id {class_id} (allowed: 0..{len(self.valid_class_ids) - 1})"
                )
                continue

            try:
                coords = [float(x) for x in tokens[1:]]
            except ValueError:
                errors.append(f"{label_path.name}:line {line_num}: coordinates must be valid floats")
                continue

            # Vertex count
            num_vertices = len(coords) // 2
            if num_vertices < 3:
                errors.append(
                    f"{label_path.name}:line {line_num}: polygon has {num_vertices} vertices, minimum 3 required"
                )
                continue

            # Check coordinate bounds [0.0, 1.0]
            out_of_bounds = False
            vertex_pairs: List[Tuple[float, float]] = []
            for i in range(0, len(coords), 2):
                vx, vy = coords[i], coords[i + 1]
                if not (-0.05 <= vx <= 1.05 and -0.05 <= vy <= 1.05):
                    errors.append(
                        f"{label_path.name}:line {line_num}: vertex ({vx:.4f}, {vy:.4f}) outside [0, 1] range"
                    )
                    out_of_bounds = True
                    break
                vertex_pairs.append((vx, vy))

            if out_of_bounds:
                continue

            # Check polygon area > 0 using Shoelace formula
            x_pts = np.array([p[0] for p in vertex_pairs])
            y_pts = np.array([p[1] for p in vertex_pairs])
            poly_area = 0.5 * np.abs(np.dot(x_pts, np.roll(y_pts, 1)) - np.dot(y_pts, np.roll(x_pts, 1)))
            if poly_area <= 1e-7:
                errors.append(
                    f"{label_path.name}:line {line_num}: degenerate/zero-area polygon (area={poly_area:.7f})"
                )
                continue

            polygons.append({
                "class_id": class_id,
                "class_name": self.class_names[class_id],
                "vertices": vertex_pairs,
                "normalized_area": float(poly_area),
            })

        is_valid = len(errors) == 0
        return is_valid, polygons, errors

    def validate_image_file(self, img_path: Path) -> Tuple[bool, Optional[str], Optional[Tuple[int, int]]]:
        """Validates format and checks for image corruption."""
        if img_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            return False, f"Unsupported format: {img_path.suffix}", None

        try:
            with Image.open(img_path) as img:
                img.verify()
            mat = cv2.imread(str(img_path))
            if mat is None:
                return False, "Corrupted image: cv2 could not decode", None
            h, w = mat.shape[:2]
            return True, None, (w, h)
        except Exception as e:
            return False, f"Corrupted image: {e}", None

    def validate_split(self, split_name: str) -> Dict[str, Any]:
        """Validates a single split directory (train, val, or test)."""
        img_dir = self.dataset_root / "images" / split_name
        lbl_dir = self.dataset_root / "labels" / split_name

        if not img_dir.is_dir() or not lbl_dir.is_dir():
            return {
                "split": split_name,
                "exists": False,
                "images_count": 0,
                "labels_count": 0,
            }

        image_files = [p for p in img_dir.iterdir() if p.is_file() and p.name != ".gitkeep"]
        label_files = [p for p in lbl_dir.iterdir() if p.is_file() and p.name != ".gitkeep"]

        img_stems = {p.stem: p for p in image_files}
        lbl_stems = {p.stem: p for p in label_files}

        missing_labels = [p.name for stem, p in img_stems.items() if stem not in lbl_stems]
        missing_images = [p.name for stem, p in lbl_stems.items() if stem not in img_stems]

        malformed_labels = []
        empty_labels = []
        corrupted_images = []
        class_distribution: Dict[str, int] = {c: 0 for c in self.class_names}
        image_hashes: Dict[str, Path] = {}
        duplicates: List[Tuple[str, str]] = []

        # Validate images
        for img_path in image_files:
            valid_img, err, _ = self.validate_image_file(img_path)
            if not valid_img:
                corrupted_images.append(f"{img_path.name}: {err}")
            else:
                try:
                    file_hash = hashlib.sha256(img_path.read_bytes()).hexdigest()
                    if file_hash in image_hashes:
                        duplicates.append((img_path.name, image_hashes[file_hash].name))
                    else:
                        image_hashes[file_hash] = img_path
                except Exception:
                    pass

        # Validate labels
        for lbl_path in label_files:
            valid_lbl, polys, errs = self.validate_segmentation_file(lbl_path)
            if not valid_lbl:
                malformed_labels.extend(errs)
            if not polys and not errs:
                empty_labels.append(lbl_path.name)
            for poly in polys:
                c_name = poly["class_name"]
                class_distribution[c_name] = class_distribution.get(c_name, 0) + 1

        return {
            "split": split_name,
            "exists": True,
            "images_count": len(image_files),
            "labels_count": len(label_files),
            "missing_labels": missing_labels,
            "missing_images": missing_images,
            "malformed_labels": malformed_labels,
            "empty_labels": empty_labels,
            "corrupted_images": corrupted_images,
            "duplicates": duplicates,
            "class_distribution": class_distribution,
            "total_annotations": sum(class_distribution.values()),
        }

    def validate_full_dataset(self) -> Dict[str, Any]:
        """Validates all splits and compiles full summary."""
        splits = ["train", "val", "test"]
        split_reports: Dict[str, Any] = {}
        total_images = 0
        total_labels = 0
        total_annotations = 0
        combined_class_dist = {c: 0 for c in self.class_names}

        for s in splits:
            rep = self.validate_split(s)
            split_reports[s] = rep
            total_images += rep.get("images_count", 0)
            total_labels += rep.get("labels_count", 0)
            total_annotations += rep.get("total_annotations", 0)
            for c, cnt in rep.get("class_distribution", {}).items():
                combined_class_dist[c] += cnt

        has_data = total_images > 0 or total_labels > 0
        status_msg = "DATASET_VALIDATED" if has_data else "NO_DATASET_SUPPLIED"

        return {
            "dataset_root": str(self.dataset_root),
            "dataset_supplied": has_data,
            "status": status_msg,
            "total_images": total_images,
            "total_labels": total_labels,
            "total_annotations": total_annotations,
            "class_distribution": combined_class_dist,
            "splits": split_reports,
        }

    def format_summary_text(self, report: Optional[Dict[str, Any]] = None) -> str:
        """Returns human-readable formatted summary string."""
        rep = report or self.validate_full_dataset()
        lines = [
            "=" * 60,
            "LIQUID WASTE SEGMENTATION DATASET VALIDATION REPORT",
            "=" * 60,
            f"Dataset Root:     {rep['dataset_root']}",
            f"Dataset Supplied: {'YES' if rep['dataset_supplied'] else 'NO (Dataset has not been supplied yet)'}",
            f"Total Images:     {rep['total_images']}",
            f"Total Labels:     {rep['total_labels']}",
            f"Total Polygons:   {rep['total_annotations']}",
            "-" * 60,
            "Class Distribution:",
        ]
        for c, count in rep["class_distribution"].items():
            lines.append(f"  - {c:<18}: {count}")

        lines.append("-" * 60)
        lines.append("Splits Detail:")
        for s_name, s_data in rep["splits"].items():
            if not s_data.get("exists", False):
                lines.append(f"  [{s_name.upper()}]: Directory not found")
                continue
            lines.append(
                f"  [{s_name.upper()}]: Images={s_data['images_count']}, "
                f"Labels={s_data['labels_count']}, "
                f"MissingLabels={len(s_data.get('missing_labels', []))}, "
                f"MalformedLabels={len(s_data.get('malformed_labels', []))}, "
                f"Corrupted={len(s_data.get('corrupted_images', []))}, "
                f"Duplicates={len(s_data.get('duplicates', []))}"
            )
        lines.append("=" * 60)
        return "\n".join(lines)


def run_validation(dataset_dir: Optional[Path] = None) -> Dict[str, Any]:
    """CLI/programmatic entry point for liquid dataset validation."""
    target = dataset_dir or (Path(__file__).resolve().parent / "liquid")
    if not target.is_dir():
        target = Path("datasets/liquid")
    validator = LiquidDatasetValidator(target)
    rep = validator.validate_full_dataset()
    print(validator.format_summary_text(rep))
    return rep


if __name__ == "__main__":
    run_validation()
