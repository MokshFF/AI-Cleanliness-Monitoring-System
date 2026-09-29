"""Phase 3 Liquid Waste Segmentation Pipeline Tests."""
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
import pytest

from ai.configs import get_liquid_classes, CONFIGS_DIR
from ai.datasets.liquid_validator import LiquidDatasetValidator
from ai.datasets.splitter import DatasetSplitter
from ai.datasets.synthetic_liquid_smoke_data import (
    create_synthetic_liquid_image,
    generate_liquid_smoke_dataset,
    generate_liquid_sample_video,
)
from ai.inference.schemas import (
    BoundingBox,
    RegionOfInterest,
    LiquidDetection,
    LiquidFrameDetectionResult,
)
from ai.inference.liquid_segmenter import LiquidWasteSegmenter, build_roi_mask

ROOT_DIR = Path(__file__).resolve().parent.parent

def test_liquid_classes_taxonomy():
    """Verify liquid waste classes order and count."""
    classes = get_liquid_classes()
    assert len(classes) == 4
    assert classes == [
        "liquid_spill",
        "sewage_overflow",
        "waterlogging",
        "drain_overflow",
    ]

def test_liquid_dataset_yaml_consistency():
    """Verify liquid_dataset.yaml exists and class names match central taxonomy."""
    import yaml
    dataset_yaml_path = CONFIGS_DIR / "liquid_dataset.yaml"
    assert dataset_yaml_path.is_file()

    with open(dataset_yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    classes = get_liquid_classes()
    assert "names" in data
    for idx, name in enumerate(classes):
        assert data["names"][idx] == name

def test_segmentation_label_parsing_valid():
    """Verify validator accepts valid YOLO segmentation polygons."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        validator = LiquidDatasetValidator(tmp_path)

        # Valid polygon with 4 vertices (8 coordinates): class 0, square in center
        valid_lbl = tmp_path / "valid_seg.txt"
        valid_lbl.write_text("0 0.20 0.20 0.40 0.20 0.40 0.40 0.20 0.40\n", encoding="utf-8")
        is_valid, polys, errors = validator.validate_segmentation_file(valid_lbl)
        assert is_valid is True
        assert len(polys) == 1
        assert polys[0]["class_name"] == "liquid_spill"
        assert polys[0]["normalized_area"] > 0
        assert len(errors) == 0

def test_invalid_polygon_detection():
    """Verify validator catches insufficient vertices, uneven tokens, and bad class IDs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        validator = LiquidDatasetValidator(tmp_path)

        # 1. Insufficient vertices (only 2 points: 4 coords -> 5 tokens total)
        line_short = tmp_path / "short.txt"
        line_short.write_text("0 0.1 0.1 0.2 0.2\n", encoding="utf-8")
        is_valid, _, errors = validator.validate_segmentation_file(line_short)
        assert is_valid is False
        assert any("insufficient tokens" in e for e in errors)

        # 2. Uneven coordinate count (odd number of coordinates, total tokens even)
        line_uneven = tmp_path / "uneven.txt"
        line_uneven.write_text("0 0.1 0.1 0.2 0.2 0.3 0.3 0.4\n", encoding="utf-8")
        is_valid, _, errors = validator.validate_segmentation_file(line_uneven)
        assert is_valid is False
        assert any("uneven coordinate count" in e for e in errors)

        # 3. Invalid class ID (e.g., 9)
        line_bad_cls = tmp_path / "bad_cls.txt"
        line_bad_cls.write_text("9 0.1 0.1 0.3 0.1 0.3 0.3\n", encoding="utf-8")
        is_valid, _, errors = validator.validate_segmentation_file(line_bad_cls)
        assert is_valid is False
        assert any("invalid class_id" in e for e in errors)

        # 4. Out-of-bounds coordinate
        line_oob = tmp_path / "oob.txt"
        line_oob.write_text("1 0.1 0.1 1.5 0.2 0.3 0.3\n", encoding="utf-8")
        is_valid, _, errors = validator.validate_segmentation_file(line_oob)
        assert is_valid is False
        assert any("outside [0, 1] range" in e for e in errors)

def test_dataset_validator_empty_liquid_dataset():
    """Verify validator handles unsupplied liquid dataset gracefully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        validator = LiquidDatasetValidator(Path(tmp_dir))
        rep = validator.validate_full_dataset()
        assert rep["dataset_supplied"] is False
        assert rep["total_images"] == 0
        summary_text = validator.format_summary_text(rep)
        assert "Dataset has not been supplied yet" in summary_text

def test_liquid_dataset_splitting():
    """Verify deterministic splitting and hash deduplication on segmentation pairs."""
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
        src_images = Path(src_dir) / "images"
        src_labels = Path(src_dir) / "labels"
        src_images.mkdir()
        src_labels.mkdir()

        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(10):
            img = dummy_img.copy()
            img[0, i] = 200
            img_file = src_images / f"liquid_{i:02d}.jpg"
            lbl_file = src_labels / f"liquid_{i:02d}.txt"
            cv2.imwrite(str(img_file), img)
            lbl_file.write_text("0 0.1 0.1 0.5 0.1 0.5 0.5 0.1 0.5\n")

        splitter = DatasetSplitter(Path(dst_dir), train_ratio=0.7, val_ratio=0.2, test_ratio=0.1, seed=42)
        res = splitter.split_dataset(src_images, src_labels, copy_files=True)
        assert res["success"] is True
        assert res["total_samples"] == 10
        assert res["train_count"] == 7
        assert res["val_count"] == 2
        assert res["test_count"] == 1

def test_liquid_inference_schemas():
    """Verify Pydantic schema validation for liquid detections and frame results."""
    roi = RegionOfInterest(name="drain_box", bbox=BoundingBox(x1=0, y1=0, x2=320, y2=240))
    det = LiquidDetection(
        class_id=2,
        class_name="waterlogging",
        confidence=0.88,
        bbox=BoundingBox(x1=50, y1=60, x2=150, y2=160),
        polygon=[[50, 60], [150, 60], [150, 160], [50, 160]],
        affected_area_pixels=10000,
        affected_area_percent=13.02,
        monitored_region_pixels=76800,
    )
    result = LiquidFrameDetectionResult(
        image_width=640,
        image_height=480,
        monitored_region_name=roi.name,
        monitored_region_pixels=76800,
        total_affected_liquid_pixels=10000,
        total_affected_area_percent=13.02,
        detections=[det],
    )
    assert result.has_violations is True
    assert result.count == 1
    assert result.detections[0].affected_area_percent == 13.02

def test_affected_area_calculation_and_roi():
    """Verify formula: affected_area_percent = (liquid_pixels / monitored_pixels) * 100."""
    h, w = 480, 640
    total_frame_pixels = h * w  # 307200

    # 1. Full frame ROI
    mask_full, pixels_full, name_full = build_roi_mask((h, w), None)
    assert pixels_full == total_frame_pixels
    assert name_full == "full_frame"

    # 2. Custom Bounding Box ROI (100x100 = 10,000 pixels)
    roi_bbox = RegionOfInterest(name="curb_roi", bbox=BoundingBox(x1=50, y1=50, x2=150, y2=150))
    mask_bbox, pixels_bbox, name_bbox = build_roi_mask((h, w), roi_bbox)
    assert pixels_bbox == 10000
    assert name_bbox == "curb_roi"

    # 3. Polygon ROI (Triangle: base 100, height 100 => area ~ 5000)
    roi_poly = RegionOfInterest(
        name="triangle_zone",
        polygon=[[0, 0], [100, 0], [0, 100]],
    )
    mask_poly, pixels_poly, name_poly = build_roi_mask((h, w), roi_poly)
    assert 4800 <= pixels_poly <= 5200

    # Verify calculation math
    liquid_pixels = 2500
    percent = (liquid_pixels / pixels_bbox) * 100.0
    assert percent == 25.0

def test_liquid_segmenter_confidence_threshold_and_prediction():
    """Verify segmenter initializes, filters confidence, and handles frames."""
    segmenter = LiquidWasteSegmenter(
        model_path="yolov8n-seg.pt",
        confidence_threshold=0.50,
        device="cpu",
    )
    assert segmenter.confidence_threshold == 0.50

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res, mask = segmenter.predict_frame(frame, frame_index=5)
    assert isinstance(res, LiquidFrameDetectionResult)
    assert res.image_width == 640
    assert res.image_height == 480
    assert res.frame_index == 5
    assert mask.shape == (480, 640)
    assert res.processing_time_ms >= 0.0

def test_synthetic_liquid_inference():
    """Verify inference pipeline processes a synthetic liquid spill image."""
    img, annots = create_synthetic_liquid_image(width=320, height=240, num_spills=1)
    assert img.shape == (240, 320, 3)
    assert len(annots) == 1

    segmenter = LiquidWasteSegmenter(model_path="yolov8n-seg.pt", confidence_threshold=0.01, device="cpu")
    res, _ = segmenter.predict_frame(img)
    assert isinstance(res, LiquidFrameDetectionResult)
    assert res.monitored_region_pixels == 320 * 240

def test_local_video_segmentation_pipeline():
    """Verify video segmentation pipeline processes frames and writes annotated video."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_video = Path(tmp_dir) / "sample_liquid.mp4"
        out_video = Path(tmp_dir) / "annotated_liquid.mp4"

        generate_liquid_sample_video(tmp_video, num_frames=5, fps=10)
        assert tmp_video.is_file()

        segmenter = LiquidWasteSegmenter(model_path="yolov8n-seg.pt", confidence_threshold=0.01, device="cpu")
        results = segmenter.detect_video(
            video_path=tmp_video,
            output_path=out_video,
            sample_rate=1,
            max_frames=5,
        )

        assert len(results) == 5
        assert out_video.is_file()
        assert out_video.stat().st_size > 0
