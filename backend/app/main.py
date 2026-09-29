"""FastAPI application initialization and lifecycle setup."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.core.logging_config import setup_logging
from backend.app.db.mongodb import async_db_manager
from backend.app.db.indexes import create_indexes
from backend.app.api.v1.router import api_router

logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: startup and shutdown."""
    logger.info("Initializing %s (v%s) in [%s] mode...", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)

    # 1. Ensure required storage directories exist
    settings.SNAPSHOT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.LOG_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.TEST_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Initialize MongoDB connection & create indexes
    try:
        is_alive = await async_db_manager.ping()
        if is_alive:
            logger.info("MongoDB connection verified. Ensuring collection indexes...")
            db = async_db_manager.get_database()
            await create_indexes(db)
        else:
            logger.warning("MongoDB ping failed on startup. Server may be offline; continuing in degraded mode.")
    except Exception as e:
        logger.warning("Database initialization warning: %s", e)

    yield

    # Shutdown
    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    async_db_manager.close()


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

# Include API v1 Routers (/api/v1/auth, /api/v1/users, /api/v1/cameras, /api/v1/incidents)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for container probes and load balancers."""
    db_alive = await async_db_manager.ping()
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected" if db_alive else "disconnected",
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
