"""Core application configuration and environment settings."""
from pathlib import Path
from typing import List, Union, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings validated against environment variables."""

    # Server & Project Info
    PROJECT_NAME: str = "AI-Based National Cleanliness Monitoring System"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    BACKEND_RELOAD: bool = True

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    # Security & JWT
    JWT_SECRET_KEY: str = "change_this_to_a_secure_random_secret_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Initial Admin Bootstrap
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@cleanliness.gov.in"
    ADMIN_PASSWORD: str = "ChangeMe@Admin2026"
    INITIAL_ADMIN_EMAIL: str = "admin@cleanliness.gov.in"
    INITIAL_ADMIN_PASSWORD: str = "ChangeMe@Admin2026"
    INITIAL_ADMIN_FULL_NAME: str = "National System Administrator"

    # Database
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "cleanliness_monitoring_db"
    MONGODB_DATABASE: Optional[str] = None
    MONGODB_MIN_POOL_SIZE: int = 5
    MONGODB_MAX_POOL_SIZE: int = 50

    @property
    def database_name(self) -> str:
        return self.MONGODB_DATABASE or self.MONGODB_DB_NAME

    # Storage
    STORAGE_BASE_DIR: Path = Path("./storage")
    SNAPSHOT_STORAGE_DIR: Path = Path("./storage/snapshots")
    LOG_STORAGE_DIR: Path = Path("./storage/logs")
    TEST_VIDEO_DIR: Path = Path("./storage/test_videos")

    # Video Ingestion
    DEFAULT_FRAME_WIDTH: int = 1280
    DEFAULT_FRAME_HEIGHT: int = 720
    TARGET_STREAM_FPS: int = 15
    PROCESS_EVERY_N_FRAMES: int = 3
    FRAME_BUFFER_MAXSIZE: int = 30
    RTSP_RECONNECT_INTERVAL_SECONDS: int = 5
    RTSP_CONNECTION_TIMEOUT_SECONDS: int = 10

    # AI Detection & Validation
    SOLID_MODEL_PATH: str = "./ai/models/weights/solid_waste_yolo.pt"
    LIQUID_MODEL_PATH: str = "./ai/models/weights/liquid_waste_yolo_seg.pt"

    # Solid Waste Tracking & Validation (Phase 5)
    SOLID_MIN_CONFIDENCE: float = 0.45
    SOLID_MIN_CONSECUTIVE_FRAMES: int = 5
    SOLID_TRACK_GRACE_FRAMES: int = 10
    SOLID_TRACK_IOU_THRESHOLD: float = 0.30

    # Liquid Waste Temporal Validation (Phase 5)
    LIQUID_MIN_CONFIDENCE: float = 0.40
    LIQUID_MIN_AFFECTED_AREA_PIXELS: int = 1200
    LIQUID_MIN_AFFECTED_AREA_PERCENT: float = 1.0
    LIQUID_AREA_CHECK_MODE: str = "OR"  # "OR", "AND", "PIXELS", "PERCENT"
    LIQUID_MIN_CONSECUTIVE_FRAMES: int = 4
    LIQUID_MIN_DURATION_SECONDS: float = 2.0

    # Incident Deduplication & Cooldown (Phase 5)
    INCIDENT_COOLDOWN_SECONDS: int = 180

    # Backwards-compatibility aliases for Phase 1 tests
    SOLID_CONFIDENCE_THRESHOLD: float = 0.45
    LIQUID_CONFIDENCE_THRESHOLD: float = 0.40
    SOLID_TEMPORAL_CONFIRMATION_FRAMES: int = 5
    LIQUID_TEMPORAL_CONFIRMATION_FRAMES: int = 4
    INCIDENT_DEDUPLICATION_COOLDOWN_SECONDS: int = 180

    # WebSockets
    WS_PING_INTERVAL_SECONDS: int = 20
    WS_PING_TIMEOUT_SECONDS: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
