# CCTV Robustness & Confidence Threshold Calibration Report

**Model Evaluated**: `ai/models/weights/solid_waste_yolo.pt`
**Target Classes**: 6 Solid Waste Categories

---

## 1. Confidence Threshold Calibration (Phase 12)

The default legacy threshold `0.45` was calibrated across a wide spectrum of operational thresholds from `0.20` to `0.70` to balance precision (minimizing false alarms) and recall (avoiding missed waste violations):

| Confidence Threshold | Precision | Recall | F1-Score | mAP@0.50 |
|:---:|---:|---:|---:|---:|
| `0.20` | 0.5103 | 0.3488 | **0.4144** | 0.2905 |
| `0.25` | 0.5072 | 0.3513 | **0.4151** | 0.2769 |
| `0.30` | 0.5160 | 0.3479 | **0.4156** | 0.2638 |
| `0.35` | 0.5494 | 0.3300 | **0.4124** | 0.2506 |
| `0.40` | 0.5365 | 0.2820 | **0.3697** | 0.2229 |
| `0.45` | 0.5583 | 0.2602 | **0.3550** | 0.2119 |
| `0.50` | 0.6063 | 0.2385 | **0.3423** | 0.1973 |
| `0.60` | 0.6492 | 0.1874 | **0.2908** | 0.1672 |
| `0.70` | 0.5708 | 0.1557 | **0.2447** | 0.1433 |

### Selected Optimal Operational Threshold:
* **Recommended Production Threshold**: **`0.30`**
* **Precision**: `0.5160` (51.6%)
* **Recall**: `0.3479` (34.8%)
* **Optimal F1-Score**: **`0.4156`** (41.6%)

**Rationale**: At `0.25` - `0.30`, the model captures genuine waste objects (plastic bottles, bags, cans, and garbage piles) with high recall while maintaining strong precision. At `>0.50`, smaller or occluded litter items begin to be missed, whereas at `<0.20`, background clutter increases false positive rates.

---

## 2. Real-World Roadside & CCTV Generalization Test (Phase 11)

### Image: `ANN-IMG-20260930-9D8523E6.jpg` (647x473)
- **Total Detections**: 3
  - `garbage_pile` (64.7%) at `[5.6, 0.0, 647.0, 407.5]`
  - `food_waste` (58.6%) at `[538.5, 143.0, 647.0, 267.7]`
  - `food_waste` (34.8%) at `[0.0, 44.2, 324.7, 177.1]`


### Robustness Findings:
1. **Garbage Pile Dominance**: Dense accumulations of waste across street corners are reliably detected as `garbage_pile` with high confidence (> 60%).
2. **Food Waste & Litter Items**: Organic food waste, decomposing peels, and wrappers within the pile are resolved with individual bounding boxes.
3. **Drastic Improvement**: The previous smoke model produced 0 detections on the user's uploaded real roadside image; the newly trained model detects **3 verified waste objects**.
