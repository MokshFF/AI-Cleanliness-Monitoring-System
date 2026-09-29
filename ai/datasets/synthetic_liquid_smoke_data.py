"""Generates synthetic liquid waste segmentation datasets and sample video for pipeline smoke-testing."""
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple
import cv2
import numpy as np

from ai.configs import get_liquid_classes

def generate_random_polygon(
    center: Tuple[int, int],
    avg_radius: int,
    irregularity: float = 0.35,
    num_vertices: int = 12,
) -> np.ndarray:
    """Generates an irregular polygon contour simulating a liquid puddle/spill."""
    cx, cy = center
    points = []
    angle_step = 2.0 * math.pi / num_vertices

    for i in range(num_vertices):
        angle = i * angle_step + random.uniform(-angle_step * 0.3, angle_step * 0.3)
        radius = avg_radius * (1.0 + random.uniform(-irregularity, irregularity))
        px = int(cx + radius * math.cos(angle))
        py = int(cy + radius * math.sin(angle))
        points.append([px, py])

    return np.array(points, dtype=np.int32)


def create_synthetic_liquid_image(
    width: int = 640,
    height: int = 480,
    num_spills: int = 2,
) -> Tuple[np.ndarray, List[Tuple[int, List[float]]]]:
    """Generates an image with simulated liquid spills, sewage, or waterlogging and returns YOLO segmentation annotations."""
    classes = get_liquid_classes()
    # Pavement asphalt ground
    base_val = random.randint(80, 110)
    image = np.full((height, width, 3), (base_val, base_val + 4, base_val + 2), dtype=np.uint8)

    # Texture noise
    noise = np.random.normal(0, 6, (height, width, 3)).astype(np.int16)
    image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    annotations: List[Tuple[int, List[float]]] = []

    # Liquid color characteristics (BGR)
    liquid_color_palette = {
        0: (60, 80, 120),    # liquid_spill (oily / chemical dark tint)
        1: (20, 45, 30),     # sewage_overflow (dark murky sludge)
        2: (110, 130, 140),  # waterlogging (reflective grayish puddle)
        3: (30, 60, 50),     # drain_overflow (dark green-brown contaminated flow)
    }

    for _ in range(num_spills):
        cls_id = random.randint(0, len(classes) - 1)
        radius = random.randint(35, 95)
        cx = random.randint(radius + 20, width - radius - 20)
        cy = random.randint(radius + 20, height - radius - 20)

        poly_pts = generate_random_polygon((cx, cy), radius, irregularity=0.35, num_vertices=random.randint(10, 16))
        # Ensure inside frame
        poly_pts[:, 0] = np.clip(poly_pts[:, 0], 5, width - 5)
        poly_pts[:, 1] = np.clip(poly_pts[:, 1], 5, height - 5)

        # Draw semi-transparent liquid blend onto surface
        overlay = image.copy()
        color = liquid_color_palette.get(cls_id, (50, 70, 70))
        cv2.fillPoly(overlay, [poly_pts], color)
        cv2.addWeighted(overlay, 0.75, image, 0.25, 0, image)

        # Normalize polygon coordinates: x1, y1, x2, y2, ...
        normalized_coords: List[float] = []
        for pt in poly_pts:
            norm_x = round(float(pt[0]) / width, 6)
            norm_y = round(float(pt[1]) / height, 6)
            normalized_coords.extend([norm_x, norm_y])

        annotations.append((cls_id, normalized_coords))

    return image, annotations


def generate_liquid_smoke_dataset(
    target_root: Path,
    num_train: int = 8,
    num_val: int = 4,
    num_test: int = 2,
) -> Dict[str, int]:
    """Populates target directory with synthetic YOLO segmentation splits."""
    target_root = Path(target_root)
    counts = {"train": num_train, "val": num_val, "test": num_test}

    for split_name, count in counts.items():
        img_dir = target_root / "images" / split_name
        lbl_dir = target_root / "labels" / split_name
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        for i in range(count):
            img, annots = create_synthetic_liquid_image()
            img_path = img_dir / f"smoke_liquid_{split_name}_{i:03d}.jpg"
            lbl_path = lbl_dir / f"smoke_liquid_{split_name}_{i:03d}.txt"

            cv2.imwrite(str(img_path), img)
            with open(lbl_path, "w", encoding="utf-8") as f:
                for cls_id, coords in annots:
                    coords_str = " ".join(f"{c:.6f}" for c in coords)
                    f.write(f"{cls_id} {coords_str}\n")

    return counts


def generate_liquid_sample_video(
    output_video_path: Path,
    num_frames: int = 30,
    fps: int = 15,
) -> Path:
    """Creates a local synthetic CCTV video with expanding waterlogging / spill for testing."""
    output_video_path = Path(output_video_path)
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    w, h = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_video_path), fourcc, fps, (w, h))

    base_frame = np.full((h, w, 3), (90, 95, 92), dtype=np.uint8)

    for i in range(num_frames):
        frame = base_frame.copy()
        # Expanding puddle: radius increases over time
        radius = int(30 + i * 2.5)
        cx, cy = 320, 260
        poly_pts = generate_random_polygon((cx, cy), radius, irregularity=0.25, num_vertices=14)

        overlay = frame.copy()
        cv2.fillPoly(overlay, [poly_pts], (45, 60, 50))  # drain/waterlogging dark tint
        cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)

        # Draw CCTV timestamp and camera header
        cv2.putText(
            frame,
            f"CAM-004 DRAIN ZONE - Frame {i:03d} (Liquid Expanding)",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1,
        )
        writer.write(frame)

    writer.release()
    return output_video_path
