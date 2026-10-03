# Real Garbage Dataset Audit Report

**Date**: 1790776717.7562072
**Dataset Name**: Garbage Classification 3 (GC1)
**Source**: Roboflow Universe / Hugging Face (`keremberke/garbage-object-detection`)
**License**: Creative Commons Attribution 4.0 International (CC BY 4.0)
**Task**: Multi-Class Bounding-Box Object Detection

---

## 1. Raw Dataset Overview

| Metric | Raw Count | Notes |
|:---|---:|:---|
| **Total Images Available** | 10464 | Real photographs of post-consumer waste |
| **Total Annotations** | 74090 | COCO-format bounding boxes |
| **Unique Scene Groups** | 10464 | Clustered by base image prefix to avoid leakage |
| **Invalid / Degenerate Boxes** | 17 | Coordinates $w \le 0$ or $h \le 0$ filtered out |
| **Tiny Artifacts (< 4px)** | 41 | Below detector resolving limit |
| **Excluded Annotations** | 7806 | Category `glass` safely excluded per taxonomy |

---

## 2. Class Taxonomy Mapping

| Source Category | Target Class ID | Target Class Name | Action / Rationale |
|:---|:---:|:---|:---|
| `biodegradable` | 4 | `food_waste` | Decomposing organic matter, fruit peels, vegetable scraps |
| `cardboard` | 2 | `paper` | Cardboard boxes, cartons, and pulp packaging |
| `paper` | 2 | `paper` | Newspapers, flyers, receipts, stationery |
| `metal` | 3 | `can` | Beverage cans, food tins, aerosol cans |
| `plastic` (elongated) | 0 | `plastic_bottle` | Cylindrical bottles, cups ($h/w \ge 1.25$ or $\le 0.70$) |
| `plastic` (flat/crumpled) | 1 | `plastic_bag` | Plastic films, carrier bags, pouches |
| `multi_waste_cluster` | 5 | `garbage_pile` | Clustered waste accumulation ($\ge 4$ items, $\ge 15\%$ area) |
| `glass` | — | *EXCLUDED* | Glass containers excluded from 6 application classes |

---

## 3. Data Splits and Leakage Prevention

To ensure true generalization:
1. **Scene Grouping**: Augmented variants containing the same base prefix (e.g. `*.rf.*`) are strictly kept within the **same partition**.
2. **Fixed Random Seed**: Deterministic partition using seed `42`.
3. **No Leakage**: Zero scene overlap across Train, Validation, and Test.

| Split | Images | Annotations | Percent of Dataset |
|:---|---:|---:|---:|
| **Train** | 380 | 2819 | ~75% |
| **Validation** | 60 | 298 | ~12.5% |
| **Test** | 60 | 279 | ~12.5% |
| **Total** | **500** | **3396** | **100%** |

---

## 4. Class Distribution Per Split

| Class ID | Class Name | Train Annotations | Val Annotations | Test Annotations | Total |
|:---:|:---|---:|---:|---:|---:|
| 0 | `plastic_bottle` | 306 | 34 | 60 | 400 |
| 1 | `plastic_bag` | 178 | 15 | 26 | 219 |
| 2 | `paper` | 251 | 29 | 16 | 296 |
| 3 | `can` | 179 | 21 | 17 | 217 |
| 4 | `food_waste` | 1802 | 184 | 146 | 2132 |
| 5 | `garbage_pile` | 103 | 15 | 14 | 132 |

---

## 5. Bounding Box & Scale Characteristics

* **Coordinate Format**: Normalized YOLO `[x_center, y_center, width, height]` in $[0.0, 1.0]$.
* **Resolution**: Standardized base images at 416x416 px resolution.
* **Small Objects**: Detected bounding boxes down to $8 	imes 8$ pixels (e.g. distant bottles, cans).
* **Medium & Large Objects**: Prominent cardboard boxes, plastic bags, and dense garbage piles.

Audit completed successfully. Ready for transfer learning training.
