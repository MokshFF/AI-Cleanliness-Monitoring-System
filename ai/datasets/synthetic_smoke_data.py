"""Generates a small synthetic dataset for smoke-testing YOLO training, validation, and video inference."""
import json
import random
from pathlib import Path
from typing import Dict, List, Tuple
import cv2
import numpy as np

from ai.configs import get_solid_classes

def create_synthetic_waste_image(
    width: int = 640,
    height: int = 720,
    num_objects: int = 3,
) -> Tuple[np.ndarray, List[Tuple[int, float, float, float, float]]]:
    """Generates an image simulating a pavement/road ground plane with waste objects and returns YOLO annotations."""
    classes = get_solid_classes()
    # Simulating asphalt/concrete pavement background
    base_color = random.randint(70, 110)
    image = np.full((height, width, 3), (base_color, base_color + 5, base_color + 3), dtype=np.uint8)

    # Add background noise/texture
    noise = np.random.normal(0, 8, (height, width, 3)).astype(np.int16)
    image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    annotations: List[Tuple[int, float, float, float, float]] = []

    for _ in range(num_objects):
        cls_id = random.randint(0, len(classes) - 1)
        w = random.randint(40, 100)
        h = random.randint(40, 120)
        x1 = random.randint(20, width - w - 20)
        y1 = random.randint(20, height - h - 20)
        x2 = x1 + w
        y2 = y1 + h

        # Draw simulated object
        color = (random.randint(50, 240), random.randint(50, 240), random.randint(50, 240))
        if cls_id == 0:  # bottle
            cv2.ellipse(image, ((x1 + x2) // 2, (y1 + y2) // 2), (w // 2, h // 2), 30, 0, 360, color, -1)
        elif cls_id == 1:  # bag
            pts = np.array([[x1, y2], [x1 + 10, y1], [x2, y1 + 15], [x2 - 10, y2]], np.int32)
            cv2.fillPoly(image, [pts], color)
        elif cls_id == 5:  # garbage pile
            cv2.circle(image, ((x1 + x2) // 2, (y1 + y2) // 2), max(w, h) // 2, (40, 40, 40), -1)
        else:
            cv2.rectangle(image, (x1, y1), (x2, y2), color, -1)

        # Convert to YOLO normalized format: xc, yc, w, h
        xc = (x1 + x2) / (2.0 * width)
        yc = (y1 + y2) / (2.0 * height)
        nw = w / width
        nh = h / height
        annotations.append((cls_id, xc, yc, nw, nh))

    return image, annotations


def generate_smoke_dataset(
    target_root: Path,
    num_train: int = 12,
    num_val: int = 4,
    num_test: int = 2,
) -> Dict[str, int]:
    """Populates target directory with small valid dataset splits for smoke testing."""
    target_root = Path(target_root)
    counts = {"train": num_train, "val": num_val, "test": num_test}

    for split_name, count in counts.items():
        img_dir = target_root / "images" / split_name
        lbl_dir = target_root / "labels" / split_name
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        for i in range(count):
            img, annots = create_synthetic_waste_image()
            img_path = img_dir / f"smoke_{split_name}_{i:03d}.jpg"
            lbl_path = lbl_dir / f"smoke_{split_name}_{i:03d}.txt"

            cv2.imwrite(str(img_path), img)
            with open(lbl_path, "w", encoding="utf-8") as f:
                for cls_id, xc, yc, w, h in annots:
                    f.write(f"{cls_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")

    return counts


def generate_sample_video(
    output_video_path: Path,
    num_frames: int = 30,
    fps: int = 15,
) -> Path:
    """Creates a local synthetic test video with motion for video inference testing."""
    output_video_path = Path(output_video_path)
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    w, h = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_video_path), fourcc, fps, (w, h))

    # Base background
    base_frame = np.full((h, w, 3), (85, 90, 88), dtype=np.uint8)

    for i in range(num_frames):
        frame = base_frame.copy()
        # Draw a moving plastic bottle (simulating discarded bottle)
        bx = int(100 + i * 4)
        by = int(180 + np.sin(i / 3.0) * 10)
        cv2.rectangle(frame, (bx, by), (bx + 50, by + 90), (0, 165, 255), -1)
        cv2.putText(frame, f"CCTV CAM-001 Frame {i}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        writer.write(frame)

    writer.release()
    return output_video_path
