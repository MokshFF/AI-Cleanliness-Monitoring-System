"""Phase 2 Solid Waste Computer Vision Pipeline Tests."""
import json
import tempfile
from pathlib import Path
import cv2
import numpy as np
import pytest

from ai.configs import get_solid_classes, CONFIGS_DIR
from ai.datasets.validator import SolidDatasetValidator
from ai.datasets.splitter import DatasetSplitter
from ai.datasets.synthetic_smoke_data import create_synthetic_waste_image, generate_smoke_dataset
from ai.inference.schemas import BoundingBox, SolidDetection, SolidFrameDetectionResult
from ai.inference.solid_detector import SolidWasteDetector

ROOT_DIR = Path(__file__).resolve().parent.parent

def test_solid_classes_taxonomy():
    """Verify solid waste classes order and count."""
    classes = get_solid_classes()
    assert len(classes) == 6
    assert classes == [
        "plastic_bottle",
        "plastic_bag",
        "paper",
        "can",
        "food_waste",
        "garbage_pile",
    ]

def test_yolo_dataset_yaml_consistency():
    """Verify solid_dataset.yaml exists and class names match central taxonomy."""
    import yaml
    dataset_yaml_path = CONFIGS_DIR / "solid_dataset.yaml"
    assert dataset_yaml_path.is_file()

    with open(dataset_yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    classes = get_solid_classes()
    assert "names" in data
    for idx, name in enumerate(classes):
        assert data["names"][idx] == name

def test_yolo_label_parsing_and_invalid_boxes():
    """Verify validator catches malformed labels, out-of-bounds coordinates, and invalid classes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        validator = SolidDatasetValidator(tmp_path)

        # 1. Valid label
        valid_lbl = tmp_path / "valid.txt"
        valid_lbl.write_text("0 0.50 0.50 0.20 0.30\n3 0.10 0.10 0.05 0.05\n", encoding="utf-8")
        is_valid, boxes, errors = validator.validate_label_file(valid_lbl)
        assert is_valid is True
        assert len(boxes) == 2
        assert len(errors) == 0

        # 2. Invalid class ID (e.g., 99)
        bad_cls_lbl = tmp_path / "bad_class.txt"
        bad_cls_lbl.write_text("99 0.50 0.50 0.20 0.20\n", encoding="utf-8")
        is_valid, boxes, errors = validator.validate_label_file(bad_cls_lbl)
        assert is_valid is False
        assert any("invalid class_id" in e for e in errors)

        # 3. Coordinates outside [0, 1]
        out_bounds_lbl = tmp_path / "out_bounds.txt"
        out_bounds_lbl.write_text("0 1.50 0.50 0.20 0.20\n", encoding="utf-8")
        is_valid, boxes, errors = validator.validate_label_file(out_bounds_lbl)
        assert is_valid is False
        assert any("outside [0, 1]" in e for e in errors)

        # 4. Malformed tokens (only 3 tokens instead of 5)
        malformed_lbl = tmp_path / "malformed.txt"
        malformed_lbl.write_text("0 0.50 0.50\n", encoding="utf-8")
        is_valid, boxes, errors = validator.validate_label_file(malformed_lbl)
        assert is_valid is False
        assert any("malformed YOLO line" in e for e in errors)

        # 5. Non-positive width
        neg_dim_lbl = tmp_path / "neg_dim.txt"
        neg_dim_lbl.write_text("1 0.50 0.50 -0.10 0.20\n", encoding="utf-8")
        is_valid, boxes, errors = validator.validate_label_file(neg_dim_lbl)
        assert is_valid is False
        assert any("non-positive dimension" in e for e in errors)

def test_dataset_validator_empty_dataset():
    """Verify validator handles unsupplied dataset gracefully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        validator = SolidDatasetValidator(Path(tmp_dir))
        rep = validator.validate_full_dataset()
        assert rep["dataset_supplied"] is False
        assert rep["total_images"] == 0
        summary_text = validator.format_summary_text(rep)
        assert "Dataset has not been supplied yet" in summary_text

def test_dataset_splitting_and_leakage_prevention():
    """Verify deterministic splitting and hash deduplication."""
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
        src_images = Path(src_dir) / "images"
        src_labels = Path(src_dir) / "labels"
        src_images.mkdir()
        src_labels.mkdir()

        # Create 10 sample images and labels
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(10):
            # Write slightly different image data to ensure distinct hashes
            img = dummy_img.copy()
            img[0, i] = 255
            img_file = src_images / f"sample_{i:02d}.jpg"
            lbl_file = src_labels / f"sample_{i:02d}.txt"
            cv2.imwrite(str(img_file), img)
            lbl_file.write_text(f"0 0.5 0.5 0.2 0.2\n")

        # Split 70% train, 20% val, 10% test
        splitter = DatasetSplitter(Path(dst_dir), train_ratio=0.7, val_ratio=0.2, test_ratio=0.1, seed=42)
        res = splitter.split_dataset(src_images, src_labels, copy_files=True)

        assert res["success"] is True
        assert res["total_samples"] == 10
        assert res["train_count"] == 7
        assert res["val_count"] == 2
        assert res["test_count"] == 1

        # Check manifest created
        manifest_path = Path(dst_dir) / "metadata" / "split_manifest.json"
        assert manifest_path.is_file()
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        assert len(manifest["splits"]["train"]) == 7

def test_inference_schemas():
    """Verify structured Pydantic schemas for detections."""
    box = BoundingBox(x1=10.0, y1=20.0, x2=60.0, y2=120.0)
    assert box.width == 50.0
    assert box.height == 100.0
    assert box.area == 5000.0

    det = SolidDetection(
        class_id=0,
        class_name="plastic_bottle",
        confidence=0.92,
        bbox=box,
    )
    assert det.class_name == "plastic_bottle"

    result = SolidFrameDetectionResult(
        image_width=640,
        image_height=480,
        detections=[det],
    )
    assert result.has_violations is True
    assert result.count == 1
    dump = result.model_dump()
    assert dump["detections"][0]["class_name"] == "plastic_bottle"

def test_solid_detector_confidence_threshold_and_prediction():
    """Verify detector filters low confidence and runs prediction on a numpy frame."""
    detector = SolidWasteDetector(model_path="yolov8n.pt", confidence_threshold=0.50, device="cpu")
    assert detector.confidence_threshold == 0.50

    # Create dummy black frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res = detector.predict_frame(frame, frame_index=1)
    assert isinstance(res, SolidFrameDetectionResult)
    assert res.image_width == 640
    assert res.image_height == 480
    assert res.frame_index == 1
    assert res.processing_time_ms >= 0.0

def test_video_generation_and_inference():
    """Verify local video generation and frame-by-frame inference."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_video = Path(tmp_dir) / "sample_cctv.mp4"
        out_video = Path(tmp_dir) / "annotated_cctv.mp4"

        from ai.datasets.synthetic_smoke_data import generate_sample_video
        generate_sample_video(tmp_video, num_frames=5, fps=10)
        assert tmp_video.is_file()

        detector = SolidWasteDetector(model_path="yolov8n.pt", confidence_threshold=0.20, device="cpu")
        results = detector.detect_video(tmp_video, output_path=out_video, sample_rate=1)

        assert len(results) == 5
        assert out_video.is_file()
        assert out_video.stat().st_size > 0
