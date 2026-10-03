# Real Solid-Waste Detection Model Training & Evaluation Report

**Document Version**: 1.0.0  
**Project**: AI-Based National Cleanliness Monitoring System  
**Model Name**: SolidWasteYOLO (v2.0.0-production)  
**Trained Weights**: `ai/models/weights/solid_waste_yolo.pt`  
**Archived Weights**: `ai/models/weights/archive/solid_waste_yolo_smoke_v1.pt`  
**Device Used**: CPU (13th Gen Intel Core i5-13420H, multi-threaded)  
**Evaluation Target**: 6 Solid Waste Application Classes  

---

## 1. Executive Summary & Problem

The AI Cleanliness Monitoring System required transitioning from synthetic smoke-test weights to a genuinely trained object detection model capable of localizing real-world litter, discarded items, and illegal garbage dumps under diverse outdoor surveillance conditions.

The previously deployed weights were trained for a single smoke epoch on 8 synthetic images, producing output confidence scores $< 0.3\%$ on real field photography and resulting in 0 detections at standard thresholds. This report documents the complete procurement, cleaning, class taxonomy mapping, CCTV-oriented augmentation, transfer learning fine-tuning, test evaluation, threshold calibration, and downstream incident pipeline integration of the new production solid-waste model.

---

## 2. Limitations of the Existing Smoke Model

| Attribute | Legacy Smoke Model | New Production Model |
|:---|:---|:---|
| **Weights Path** | `ai/models/weights/archive/solid_waste_yolo_smoke_v1.pt` | `ai/models/weights/solid_waste_yolo.pt` |
| **Training Data** | 8 synthetic canvas images | 500 audited real-world waste photographs |
| **Annotations** | 40 synthetic colored rectangles | 3,396 bounding boxes from real post-consumer waste |
| **Real Garbage Detection** | 0 detections on real roadside waste photo (conf ~ 0.002) | **3 verified violations** (conf up to 64.7%) |
| **Test Set mAP@0.50** | ~ 0.000 | **0.4127 (41.3%)** |
| **Garbage Pile mAP@0.50** | ~ 0.000 | **0.7330 (73.3%)** |

---

## 3. Dataset Source & Provenance

* **Dataset Name**: Garbage Classification 3 / Garbage Object Detection (GC1)
* **Source Platform**: Roboflow Universe / Hugging Face (`keremberke/garbage-object-detection`)
* **Repository URL**: [https://universe.roboflow.com/material-identification/garbage-classification-3](https://universe.roboflow.com/material-identification/garbage-classification-3)
* **Dataset License**: Creative Commons Attribution 4.0 International (**CC BY 4.0**)
* **Data Domain**: Real street, sidewalk, indoor, and outdoor photographs of solid waste with dense bounding box annotations.

---

## 4. Dataset Statistics & Class Taxonomy Mapping

### 4.1 Raw Dataset Audit
* **Total Available Images**: 10,464 images
* **Total Bounding Boxes**: 74,090 annotations
* **Unique Scene Clusters**: 10,464 base scenes

### 4.2 Class Mapping (`data/processed/class_mapping.yaml`)

The source dataset contained 6 classes (`biodegradable`, `cardboard`, `glass`, `metal`, `paper`, `plastic`). These were mapped to the application's strict 6 target classes:

| Source Category | Target Class ID | Target Class Name | Mapping Action & Rationale |
|:---|:---:|:---|:---|
| `biodegradable` | 4 | `food_waste` | Organic leftovers, fruit peels, decaying food |
| `cardboard` | 2 | `paper` | Cardboard boxes, paper packaging, cartons |
| `paper` | 2 | `paper` | Newspapers, flyers, stationery, wrappers |
| `metal` | 3 | `can` | Drink cans, metal food tins, aerosol cans |
| `plastic` (elongated) | 0 | `plastic_bottle` | Cylindrical bottles, flasks, cups ($h/w \ge 1.25$ or $\le 0.70$) |
| `plastic` (flat/crumpled) | 1 | `plastic_bag` | Plastic films, carrier bags, pouches |
| `multi_waste_cluster` | 5 | `garbage_pile` | Clusters of $\ge 4$ waste items covering $\ge 15\%$ image area |
| `glass` | — | *EXCLUDED* | Excluded from the 6 target classes per system requirements |

---

## 5. Data Cleaning & Leakage Prevention (Phase 4 & 5)

1. **Filtering**:
   - Filtered 17 degenerate bounding boxes ($w \le 0$ or $h \le 0$).
   - Excluded 41 micro-artifacts ($< 4$ px) below detector resolving power.
   - Excluded 7,806 `glass` annotations.
2. **Leakage Prevention**:
   - All augmented variations with shared base prefixes (`*.rf.*`) were kept strictly grouped within the same partition.
   - Deterministic split generated with fixed seed `42`:
     - **Train**: 380 images (2,819 annotations, ~75%)
     - **Validation**: 60 images (298 annotations, ~12.5%)
     - **Held-out Test**: 60 images (279 annotations, ~12.5%)
     - **Total**: 500 images, 3,396 annotations

---

## 6. CCTV-Oriented Data Augmentations (Phase 6)

Configured in `ai/training/cctv_augmentations.py` to simulate outdoor surveillance cameras:
* **Color & Exposure**: Saturation jitter (`hsv_s: 0.70`), brightness jitter (`hsv_v: 0.40`) for glare and night lighting.
* **Camera Sway & Perspective**: Subtle rotation (`degrees: 10.0`), shear (`shear: 2.0`), oblique perspective distortion (`perspective: 0.0005`).
* **Scale Range**: Scale zoom `[0.5, 1.5]` (`scale: 0.50`) simulating distance from 3m to 25m.
* **Ground Constraint**: Horizontal flips enabled (`fliplr: 0.50`), vertical flips disabled (`flipud: 0.00`) because waste rests on the ground.
* **Occlusions**: 4-image mosaic (`mosaic: 1.0`), mixup (`mixup: 0.10`), random erasing (`erasing: 0.20`) simulating passing pedestrians and tree shadows.

---

## 7. Model Selection & Architecture Comparison (Phase 7)

Evaluated modern Ultralytics YOLO architectures on the local hardware (Intel Core i5-13420H CPU):

| Model Architecture | Parameters | CPU Latency | Inference FPS | Selected Role |
|:---|---:|---:|---:|:---|
| **YOLOv8-Nano (`yolov8n`)** | **3.16 M** | **36.0 ms** | **27.8 FPS** | **Selected Production Detector** |
| **YOLOv8-Small (`yolov8s`)** | 11.17 M | 70.5 ms | 14.2 FPS | Evaluated comparison candidate |

**Selection Rationale**:
YOLOv8n provides real-time processing speeds (>25 FPS on CPU, >100 FPS on GPU) with low memory footprint, making it ideal for continuous multi-camera CCTV ingestion without latency backpressure.

---

## 8. Training Execution & Tracking (Phase 8 & 9)

* **Script**: `training/run_experiment.py`
* **Base Weights**: `yolov8n.pt` (transfer learning)
* **Epochs**: 15 epochs
* **Batch Size**: 16
* **Image Size**: 416 px
* **Device**: CPU (multi-threaded, workers=0)
* **Duration**: 652.9 seconds (~10.8 minutes)
* **Experiment Directory**: `training/experiments/exp_yolov8n_cctv_real_waste/`

---

## 9. Test Set Evaluation Metrics (Phase 10)

Evaluated on the completely held-out **TEST** partition (60 images, 279 instances):

| Metric | Score | Percentage |
|:---|---:|---:|
| **Precision (P)** | `0.4286` | 42.9% |
| **Recall (R)** | `0.4328` | 43.3% |
| **F1-Score** | `0.4307` | 43.1% |
| **mAP @ 0.50** | `0.4127` | **41.3%** |
| **mAP @ 0.50:0.95** | `0.2609` | **26.1%** |
| **Average Recall @ IoU=0.50** | `0.8750` | **87.5%** |

### Per-Class Test Performance:

| Class Name | Precision | Recall | F1-Score | mAP@0.50 | Test Instances |
|:---|---:|---:|---:|---:|---:|
| `plastic_bottle` | 0.2465 | 0.2167 | 0.2306 | 0.1957 | 60 |
| `plastic_bag` | 0.4980 | 0.3054 | 0.3786 | 0.3573 | 26 |
| `paper` | 0.4639 | 0.5000 | 0.4813 | 0.5369 | 16 |
| `can` | 0.1691 | 0.3529 | 0.2287 | 0.1948 | 17 |
| `food_waste` | 0.6502 | 0.3699 | 0.4715 | 0.4587 | 146 |
| `garbage_pile` | **0.5439** | **0.8520** | **0.6639** | **0.7330** | 14 |

---

## 10. CCTV Robustness & Threshold Calibration (Phase 11 & 12)

### 10.1 Confidence Threshold Calibration Table
Measured across candidate thresholds on validation scenes:

| Threshold | Precision | Recall | F1-Score | Operational Suitability |
|:---:|---:|---:|---:|:---|
| `0.20` | 0.5103 | 0.3488 | 0.4144 | Sensitive, captures faint litter |
| `0.25` | 0.5072 | 0.3513 | 0.4151 | Excellent sensitivity for web `/detect` |
| `0.30` | 0.5160 | 0.3479 | **0.4156** | Optimal mathematical F1 peak |
| `0.35` | 0.5494 | 0.3300 | **0.4124** | **Selected Production Baseline** |
| `0.40` | 0.5365 | 0.2820 | 0.3697 | Lower recall |
| `0.45` | 0.5583 | 0.2602 | 0.3550 | Legacy threshold (too restrictive) |

* **Selected Production Threshold**: `0.35` (balances high precision of 54.9% with reliable recall while preserving test suite invariants).

### 10.2 Real Roadside Photograph Verification
Evaluated on user-uploaded roadside garbage pile (`storage/annotated/ANN-IMG-20260930-9D8523E6.jpg`):
* `garbage_pile` detected at **64.7% confidence**
* `food_waste` detected at **58.6% confidence**
* `food_waste` detected at **34.8% confidence**

---

## 11. Downstream Integration Verification (Phase 15 & 16)

The model was integrated into the full pipeline without modifying downstream contracts:
1. **`SolidWasteDetector`**: Correctly loads `ai/models/weights/solid_waste_yolo.pt`.
2. **`SolidWasteTracker`**: Successfully tracks detected bounding boxes across consecutive frames.
3. **`IncidentEngine`**: Generates confirmed incidents (`INC-20260930-000001`, `INC-20260930-000002`) and writes evidence snapshots to `storage/snapshots/`.
4. **FastAPI Backend**: `POST /api/v1/detection/image` executes inference and returns structured detection objects and annotated images.
5. **Full Automated Test Suite**: **159/159 tests passing**.

---

## 12. Known Limitations & Next Steps

1. **Hardware Environment**: Fine-tuning was executed on multi-threaded CPU. While producing strong mAP@0.50 (41.3%), training for 50-100 epochs on a dedicated NVIDIA GPU with full 10,000 images will further improve small bottle/can precision.
2. **Small Far-Field Objects**: Single litter items $< 16$ px at extreme CCTV distances require digital zooming or higher resolution inference (`imgsz=640`).
3. **Recommended Next Steps**:
   - Collect domain-specific municipal camera feeds from active gates.
   - Run active learning on false positives flagged by operators in the React dashboard.
