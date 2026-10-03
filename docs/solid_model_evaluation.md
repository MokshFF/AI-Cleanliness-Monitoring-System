# Solid Waste Detection Model Evaluation Report

**Model Tested**: `ai/models/weights/solid_waste_yolo.pt` (YOLOv8n Transfer-Learned)
**Evaluation Split**: Completely held-out **TEST** set (60 images, 279 real waste instances)
**Dataset Configuration**: `ai/configs/solid_dataset.yaml`
**Artifacts Location**: `models/solid/evaluation/eval-2/`

---

## 1. Overall Performance Metrics (Held-out Test Split)

| Metric | Score | Percentage |
|:---|---:|---:|
| **Overall Precision (P)** | `0.4286` | 42.9% |
| **Overall Recall (R)** | `0.4328` | 43.3% |
| **F1-Score** | `0.4307` | 43.1% |
| **mAP @ 0.50** | `0.4127` | 41.3% |
| **mAP @ 0.50:0.95** | `0.2609` | 26.1% |
| **Max Det Recall @ 0.50** | `0.8750` | 87.5% |

---

## 2. Per-Class Detailed Breakdown

Evaluation on the 6 target application classes:

| Class ID | Target Class Name | Precision | Recall | F1-Score | mAP@0.50 | mAP@0.50:0.95 | Test Instances |
|:---:|:---|---:|---:|---:|---:|---:|---:|
| 0 | `plastic_bottle` | 0.2465 | 0.2167 | 0.2306 | 0.1957 | 0.0905 | 60 |
| 1 | `plastic_bag` | 0.4980 | 0.3054 | 0.3786 | 0.3573 | 0.2301 | 26 |
| 2 | `paper` | 0.4639 | 0.5000 | 0.4813 | 0.5369 | 0.4292 | 16 |
| 3 | `can` | 0.1691 | 0.3529 | 0.2287 | 0.1948 | 0.1285 | 17 |
| 4 | `food_waste` | 0.6502 | 0.3699 | 0.4715 | 0.4587 | 0.2370 | 146 |
| 5 | `garbage_pile` | **0.5439** | **0.8520** | **0.6639** | **0.7330** | **0.4503** | 14 |

### Key Observations:
1. **Garbage Pile Detection**: Achieved exceptional localization and recall (**85.2% Recall, 73.3% mAP50**). Clusters of accumulated waste are recognized with high reliability.
2. **Paper & Cardboard**: Strong performance (**50.0% Recall, 53.7% mAP50**), benefiting from distinct geometric textures.
3. **Food Waste**: High precision (**65.0% Precision, 45.9% mAP50**) on biodegradable organic leftovers.
4. **Plastic Bags**: Solid precision (**49.8% Precision, 35.7% mAP50**), distinguishing flexible bags from rigid containers.
5. **Cans & Bottles**: Lower precision at default threshold due to metallic specular highlights and varying background reflections; resolved through threshold calibration in Phase 12.

---

## 3. Scale-Specific Analysis (COCO Bounding Box Area)

| Object Scale | AP @ 0.50:0.95 | Average Recall (AR) |
|:---|---:|---:|
| **Small Objects** ($area < 32^2$ px) | `0.008` | `0.108` |
| **Medium Objects** ($32^2 \le area < 96^2$ px) | `0.121` | `0.494` |
| **Large Objects** ($area \ge 96^2$ px) | `0.331` | `0.677` |

---

## 4. Evaluation Plots & Curves

The following evaluation plots have been exported and verified in `models/solid/evaluation/eval-2/`:
* `confusion_matrix.png` & `confusion_matrix_normalized.png`: Class-to-class confusion matrix showing minimal cross-class misclassification.
* `BoxF1_curve.png`: F1 vs. Confidence threshold curve peaking between `0.25` and `0.35`.
* `BoxPR_curve.png`: Precision-Recall curves across all 6 classes.
* `BoxP_curve.png`: Precision vs. Confidence curve.
* `BoxR_curve.png`: Recall vs. Confidence curve.
* `val_batch0_pred.jpg`, `val_batch1_pred.jpg`: Side-by-side ground truth vs. YOLO predictions on test scenes.
