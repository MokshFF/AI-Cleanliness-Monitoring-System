"""CCTV-specific data augmentation parameters for Liquid Waste instance segmentation.

Rationale for Liquid Surveillance:
1. Reflection & Lighting (hsv_v, hsv_s):
   Liquids exhibit glare under sunlight and dull gray-brown characteristics during overcast rain or at night.
2. Perspective & Low Camera Angles:
   Street-level or wall-mounted CCTV captures puddles and drain spills at oblique angles.
3. Scale Range (scale=0.5):
   Spills vary in visual scale from small pipe leaks to large road waterlogging.
4. Vertical Inversion Prohibition (flipud=0.0):
   Water pools horizontally; vertical flipping would simulate puddles defying gravity.
5. Mild Occlusion:
   Pedestrians or vehicles partially blocking view of the flooded road.
"""
from typing import Dict, Any

def get_liquid_cctv_augmentation_config() -> Dict[str, Any]:
    """Returns Ultralytics YOLO-compatible training hyperparameters for liquid segmentation."""
    return {
        # Color & lighting variation
        "hsv_h": 0.020,   # Mild hue variations (muddy/chemical water)
        "hsv_s": 0.600,   # Saturation variation (dull vs reflective)
        "hsv_v": 0.400,   # Glare, shadows, streetlamps

        # Geometric & Perspective
        "degrees": 8.0,    # Modest rotation
        "translate": 0.08, # Minor panning
        "scale": 0.50,     # Zoom range [0.5, 1.5]
        "shear": 2.0,
        "perspective": 0.0008, # Oblique pavement angle

        # Flips
        "fliplr": 0.50,    # Horizontal flip
        "flipud": 0.00,    # Strictly disabled

        # Multi-scale & Occlusion
        "mosaic": 1.00,    # Composite multi-scene context
        "mixup": 0.10,     # Shadow / water transparency blend
        "erasing": 0.20,   # Occlusion by curb, foot traffic
    }
