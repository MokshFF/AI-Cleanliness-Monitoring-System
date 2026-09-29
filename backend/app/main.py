"""FastAPI application initialization and lifecycle setup."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.core.config import settings
from backend.app.core.logging_config import setup_logging

logger = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: startup and shutdown."""
    logger.info("Initializing %s (v%s) in [%s] mode...", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)
    # Ensure storage folders exist
    settings.SNAPSHOT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.LOG_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.TEST_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    yield
    logger.info("Shutting down %s...", settings.PROJECT_NAME)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-grade AI-powered Cleanliness Monitoring Platform for Solid and Liquid Waste",
    lifespan=lifespan,
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount evidence snapshots directory as static files
settings.SNAPSHOT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=str(settings.SNAPSHOT_STORAGE_DIR)), name="snapshots")

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for container probes and load balancers."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }

@app.get(f"{settings.API_V1_PREFIX}/status", tags=["Status"])
async def system_status():
    """Returns general system status and active configuration modes."""
    return {
        "status": "operational",
        "debug": settings.DEBUG,
        "supported_waste_types": ["solid", "liquid"],
        "solid_classes": [
            "plastic_bottle", "plastic_bag", "paper", "can", "food_waste", "garbage_pile"
        ],
        "liquid_classes": [
            "liquid_spill", "sewage_overflow", "waterlogging", "drain_overflow"
        ],
    }
