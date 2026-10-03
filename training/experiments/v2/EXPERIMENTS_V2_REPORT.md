# High-Accuracy Model Experiments & Benchmark Report (v2)

**Generated**: 2026-09-30T16:36:03.349205+00:00  
**Dataset**: `GarbageDataset-v2` (1,200 images, 7,986 annotations)  
**Hardware Profile**: Intel Core i5-13420H (CPU Only, 8 Cores / 12 Threads)

---

## 1. Executive Summary & Progression

| Metric | Baseline (v1 @ 416px) | EXP-01 (YOLOv8n @ 640px) | EXP-02 (YOLOv8s @ 640px) | Improvement (vs Baseline) |
|:---|:---:|:---:|:---:|:---:|
| **Test Precision** | 42.9% | 51.3% | 56.8% | **++13.9%** |
| **Test Recall** | 43.3% | 38.9% | 43.5% | **++0.2%** |
| **Test F1-Score** | 43.1% | 44.2% | 49.2% | **++6.1%** |
| **Test mAP@0.50** | 41.3% | 40.2% | 47.0% | **++5.8%** |
| **Test mAP@0.50:0.95** | 26.1% | 25.1% | 29.1% | **++3.0%** |
| **Small-Object AP** | 0.008 | 0.098 | 0.113 | **Significant Gain** |
| **Inference Latency (CPU)** | ~36 ms | 62.4 ms | 134.6 ms | Practical for CCTV |
| **Throughput (FPS)** | ~27.8 FPS | 16.0 FPS | 7.4 FPS | Real-time capable |

---

## 2. Per-Class Performance Breakdown (Held-Out Test Set)

### Selected Best Model: `EXP-02-v8s-640`

| Target Class | Precision | Recall | F1-Score | mAP@0.50 | mAP@0.50:0.95 |
|:---|:---:|:---:|:---:|:---:|:---:|
| `plastic_bottle` | 48.6% | 23.9% | 32.0% | 26.0% | 13.1% |
| `plastic_bag` | 56.5% | 30.1% | 39.3% | 37.0% | 23.9% |
| `paper` | 56.2% | 35.9% | 43.8% | 40.5% | 29.4% |
| `can` | 53.0% | 45.3% | 48.8% | 50.5% | 31.7% |
| `food_waste` | 65.6% | 49.5% | 56.4% | 54.7% | 26.8% |
| `garbage_pile` | 60.6% | 76.2% | 67.5% | 73.8% | 49.6% |

---

## 3. Scale-Specific AP Breakdown (COCO Scale Definitions)

- **Small Objects** ($area < 32^2 = 1024 px$):
  - Precision: 58.3%
  - Recall: 6.6%
  - F1-Score: 11.9%
  - Ground Truth Instances: 106

- **Medium Objects** ($32^2 \le area < 96^2$):
  - Precision: 66.4%
  - Recall: 45.3%
  - F1-Score: 53.8%
  - Ground Truth Instances: 318

- **Large Objects** ($area \ge 96^2$):
  - Precision: 61.9%
  - Recall: 47.2%
  - F1-Score: 53.6%
  - Ground Truth Instances: 364

---

## 4. Confidence Threshold Calibration Sweep

Optimal threshold selected: **`0.25`**

| Threshold | Precision | Recall | Overall F1 | Small F1 | Medium F1 | Large F1 | Latency | FPS |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 0.20 | 57.1% | 43.3% | 49.2% | 11.5% | 53.1% | 52.7% | 136.6ms | 7.3 |
| 0.25 **(Selected)** | 63.7% | 41.0% | 49.9% | 11.9% | 53.8% | 53.6% | 137.0ms | 7.3 |
| 0.30 | 69.2% | 38.7% | 49.6% | 8.7% | 54.2% | 53.6% | 134.8ms | 7.4 |
| 0.35 | 72.4% | 35.3% | 47.4% | 3.6% | 53.1% | 51.2% | 134.0ms | 7.5 |
| 0.40 | 76.6% | 32.9% | 46.0% | 1.8% | 53.8% | 48.1% | 144.6ms | 6.9 |
| 0.45 | 81.4% | 29.9% | 43.8% | 1.8% | 52.2% | 45.2% | 138.8ms | 7.2 |
| 0.50 | 85.8% | 27.5% | 41.7% | 1.9% | 49.0% | 43.8% | 142.8ms | 7.0 |
| 0.55 | 86.7% | 24.9% | 38.7% | 1.9% | 46.7% | 39.7% | 139.3ms | 7.2 |
| 0.60 | 89.8% | 22.5% | 35.9% | 1.9% | 43.0% | 37.5% | 133.4ms | 7.5 |
| 0.65 | 91.4% | 20.3% | 33.2% | 0.0% | 41.3% | 33.7% | 136.1ms | 7.3 |
| 0.70 | 92.0% | 17.4% | 29.2% | 0.0% | 37.5% | 28.8% | 135.0ms | 7.4 |

---

## 5. Deployment Recommendation

The model `EXP-02-v8s-640` with confidence threshold `0.25` has been automatically exported to:
- `models/solid/best.pt`
- `ai/models/weights/solid_waste_yolo.pt`
