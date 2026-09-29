"""CCTV-specific augmentation configurations for Solid Waste detection.

Augmentation rationale for CCTV/surveillance streams:
1. Brightness & Contrast (hsv_v, hsv_s):
   Simulates harsh sunlight, dusk, overcast weather, and night-time security lighting.
2. Moderate Perspective & Rotation (degrees=10.0, translate=0.10):
   Simulates pole-mounted camera sway, varying oblique viewing angles, and camera lens distortions.
3. Scaling (scale=0.50):
   Crucial for CCTV where discarded bottles/bags can appear from close-range (3m) to far-field (25m).
4. Flips (fliplr=0.5, flipud=0.0):
   Horizontal flipping is valid; vertical flipping is disabled to prevent upside-down roads/lawns.
5. Mosaic & Mixup (mosaic=1.0, mixup=0.10):
   Simulates occlusions from passing pedestrians, shadows, and foliage.
"""
from typing import Dict, Any

def get_cctv_augmentation_config() -> Dict[str, Any]:
    """Returns Ultralytics YOLO-compatible training hyperparameters optimized for CCTV footage."""
    return {
        # Color & lighting variation
        "hsv_h": 0.015,   # Hue variation
        "hsv_s": 0.700,   # Saturation variation (dull rain vs vivid sun)
        "hsv_v": 0.400,   # Value/brightness variation (glare, shadow)

        # Spatial / Geometric
        "degrees": 10.0,   # Gentle rotation (+/- 10 deg)
        "translate": 0.10, # Minor translation jitter
        "scale": 0.50,     # Zoom range [0.5, 1.5] for distance variation
        "shear": 2.0,      # Small shear angle
        "perspective": 0.0005, # Oblique angle simulation

        # Flips
        "fliplr": 0.50,    # Horizontal flip
        "flipud": 0.00,    # Strictly disabled: waste rests on ground

        # Composite & Occlusion
        "mosaic": 1.00,    # 4-image mosaic for multi-scale context
        "mixup": 0.10,     # Low-opacity image blend for shadow resilience
        "copy_paste": 0.05,# Paste small objects
        "erasing": 0.20,   # Random rectangle erasing (pedestrian/vehicle occlusions)
    }
