"""Structured logging configuration for backend, video processing, and AI inference."""
import logging
import sys
from pathlib import Path
from backend.app.core.config import settings

def setup_logging() -> logging.Logger:
    """Configures root and application loggers with console and file handlers."""
    log_dir = Path(settings.LOG_STORAGE_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "cleanliness_system.log"

    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # File Handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

    logger = logging.getLogger("cleanliness_system")
    return logger
