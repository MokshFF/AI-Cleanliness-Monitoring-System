"""Video processing, RTSP ingestion, frame buffering, and camera stream management."""
from pathlib import Path

VIDEO_DIR = Path(__file__).resolve().parent

__all__ = ["VIDEO_DIR"]
