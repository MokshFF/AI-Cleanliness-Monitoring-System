"""Solid Waste Dataset Validation Utility.

Detects:
- Missing images or labels
- Malformed YOLO label lines
- Invalid class IDs
- Invalid bounding boxes (width/height <= 0, outside [0, 1])
- Empty annotation files
- Duplicate image files (SHA-256 hash matching)
- Unsupported or corrupted image files
- Per-class annotation distribution
"""
import hashlib
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

# Ensure project root is in sys.path for direct CLI script execution
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PIL import Image
import cv2
from ai.configs import get_solid_classes

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

class SolidDatasetValidator:
    """Validates YOLO formatted dataset against cleanliness solid waste taxonomy."""

    def __init__(self, dataset_root: Path, class_names: Optional[List[str]] = None) -> None:
        self.dataset_root = Path(dataset_root)
        self.class_names = class_names or get_solid_classes()
        self.valid_class_ids = set(range(len(self.class_names)))

    def validate_label_file(
        self, label_path: Path
    ) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
        """Parses and validates a single YOLO label file.
        
        Returns:
            (is_valid, parsed_boxes, error_messages)
        """
        boxes: List[Dict[str, Any]] = []
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
            if len(tokens) != 5:
                errors.append(
                    f"{label_path.name}:line {line_num}: malformed YOLO line, expected 5 tokens, got {len(tokens)}"
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
                xc, yc, w, h = map(float, tokens[1:5])
            except ValueError:
                errors.append(f"{label_path.name}:line {line_num}: coordinates must be valid floats")
                continue

            # Coordinate range check [0, 1]
            if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0):
                errors.append(
                    f"{label_path.name}:line {line_num}: center coordinates ({xc:.4f}, {yc:.4f}) outside [0, 1]"
                )
                continue

            if w <= 0.0 or h <= 0.0:
                errors.append(
                    f"{label_path.name}:line {line_num}: non-positive dimension (width={w:.4f}, height={h:.4f})"
                )
                continue

            if w > 1.0 or h > 1.0:
                errors.append(
                    f"{label_path.name}:line {line_num}: dimension exceeds 1.0 (width={w:.4f}, height={h:.4f})"
                )
                continue

            # Boundary overflow check with tolerance
            x1 = xc - w / 2.0
            y1 = yc - h / 2.0
            x2 = xc + w / 2.0
            y2 = yc + h / 2.0
            if x1 < -0.05 or y1 < -0.05 or x2 > 1.05 or y2 > 1.05:
                errors.append(
                    f"{label_path.name}:line {line_num}: bounding box [{x1:.2f}, {y1:.2f}, {x2:.2f}, {y2:.2f}] extends outside frame"
                )
                continue

            boxes.append({
                "class_id": class_id,
                "class_name": self.class_names[class_id],
                "bbox": [xc, yc, w, h],
            })

        is_valid = len(errors) == 0
        return is_valid, boxes, errors

    def validate_image_file(self, img_path: Path) -> Tuple[bool, Optional[str], Optional[Tuple[int, int]]]:
        """Validates format and checks for image corruption.
        
        Returns:
            (is_valid, error_message, (width, height))
        """
        if img_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            return False, f"Unsupported format: {img_path.suffix}", None

        try:
            with Image.open(img_path) as img:
                img.verify()
            # Double check with cv2 decode
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
        invalid_class_ids = []
        invalid_boxes = []
        empty_labels = []
        corrupted_images = []
        class_distribution: Dict[str, int] = {c: 0 for c in self.class_names}
        image_hashes: Dict[str, Path] = {}
        duplicates: List[Tuple[str, str]] = []

        # Validate images & check duplicate hashes
        for img_path in image_files:
            valid_img, err, dims = self.validate_image_file(img_path)
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
            valid_lbl, boxes, errs = self.validate_label_file(lbl_path)
            if not valid_lbl:
                malformed_labels.extend(errs)
            if not boxes and not errs:
                empty_labels.append(lbl_path.name)
            for box in boxes:
                c_name = box["class_name"]
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
        """Validates all splits (train, val, test) and generates a complete audit report."""
        splits = ["train", "val", "test"]
        split_reports: Dict[str, Any] = {}
        total_images = 0
        total_labels = 0
        total_annotations = 0
        combined_class_dist = {c: 0 for c in self.class_names}

        dataset_exists = (self.dataset_root / "images").is_dir()

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

        report = {
            "dataset_root": str(self.dataset_root),
            "dataset_supplied": has_data,
            "status": status_msg,
            "total_images": total_images,
            "total_labels": total_labels,
            "total_annotations": total_annotations,
            "class_distribution": combined_class_dist,
            "splits": split_reports,
        }
        return report

    def format_summary_text(self, report: Optional[Dict[str, Any]] = None) -> str:
        """Returns human-readable formatted summary string."""
        rep = report or self.validate_full_dataset()
        lines = [
            "=" * 60,
            "SOLID WASTE DATASET VALIDATION REPORT",
            "=" * 60,
            f"Dataset Root:     {rep['dataset_root']}",
            f"Dataset Supplied: {'YES' if rep['dataset_supplied'] else 'NO (Dataset has not been supplied yet)'}",
            f"Total Images:     {rep['total_images']}",
            f"Total Labels:     {rep['total_labels']}",
            f"Total Boxes:      {rep['total_annotations']}",
            "-" * 60,
            "Class Distribution:",
        ]
        for c, count in rep["class_distribution"].items():
            lines.append(f"  - {c:<16}: {count}")

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
    """CLI/programmatic entry point for dataset validation."""
    target = dataset_dir or (Path(__file__).resolve().parent / "solid")
    validator = SolidDatasetValidator(target)
    rep = validator.validate_full_dataset()
    print(validator.format_summary_text(rep))
    return rep


if __name__ == "__main__":
    run_validation()
