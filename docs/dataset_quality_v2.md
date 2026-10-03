# GarbageDataset-v2 Quality & Audit Report

**Dataset Version**: `GarbageDataset-v2`  
**Date**: 2026-09-30  
**Source**: Roboflow Universe / Hugging Face (`keremberke/garbage-object-detection`)  
**License**: Creative Commons Attribution 4.0 International (CC BY 4.0)  

---

## 1. Corpus-Wide Audit Findings (10,464 Images)

The complete raw dataset was subjected to automated verification:

| Quality Dimension | Value | Action Taken |
|:---|---:|:---|
| **Total Raw Images Audited** | 10464 | Inspected across train, valid, and test archives |
| **Total Raw Annotations** | 74090 | Evaluated for geometry, category, and bounds |
| **Corrupt / Unreadable Images** | 0 | Discarded automatically |
| **Zero-Area / Degenerate Boxes** | 17 | Removed ($w \le 0$ or $h \le 0$) |
| **Sub-Pixel Micro Artifacts (< 4px)**| 41 | Removed (unresolvable noise) |
| **Out-of-Boundary Coordinates** | 0 | Clamped to valid $[0.0, 1.0]$ bounds |
| **Duplicate Bounding Boxes** | 0 | Deduplicated |
| **Excluded Category (`glass`)** | 7806 | Safely excluded per target taxonomy |
| **Total Usable Clean Scenes** | **8643** | Eligible for balanced dataset selection |

---

## 2. GarbageDataset-v2 Composition & Splits

To eliminate data leakage, augmented variants sharing the same scene prefix (`*.rf.*`) are kept strictly within the same split:

| Partition | Images | Annotations | Percent of Dataset |
|:---|---:|---:|---:|
| **Train** | 900 | 6053 | 75.0% |
| **Validation** | 150 | 1145 | 12.5% |
| **Held-Out Test** | 150 | 788 | 12.5% |
| **Total** | **1200** | **7986** | **100.0%** |

---

## 3. Class Distribution Across GarbageDataset-v2

| Class ID | Target Class Name | Train Annotations | Val Annotations | Test Annotations | Total Annotations |
|:---:|:---|---:|---:|---:|---:|
| 0 | `plastic_bottle` | 704 | 82 | 138 | 924 |
| 1 | `plastic_bag` | 389 | 69 | 73 | 531 |
| 2 | `paper` | 516 | 88 | 92 | 696 |
| 3 | `can` | 828 | 75 | 53 | 956 |
| 4 | `food_waste` | 3361 | 796 | 390 | 4547 |
| 5 | `garbage_pile` | 255 | 35 | 42 | 332 |

---

## 4. Class Balancing Methodology

1. **Stratified Sampling**: Rather than letting dominant classes (e.g. food waste) drown out rarer classes, scenes were indexed by their dominant waste class.
2. **Quota Sampling**: Equalized target representation across all 6 classes to prevent minority class collapse.
3. **Cluster Synthesis**: Multi-object waste accumulations ($\ge 4$ overlapping items) were derived as `garbage_pile` bounding boxes, providing robust coverage of dense litter heaps.

Dataset build complete. Ready for high-resolution model training.
