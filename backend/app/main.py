import asyncio
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.core.logging_config import setup_logging
from backend.app.db.mongodb import async_db_manager
from backend.app.db.indexes import create_indexes
from backend.app.api.v1.router import api_router
from backend.app.websocket.manager import get_connection_manager
from backend.app.api.v1.websocket import handle_websocket_alerts

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
            logger.warning(
                "MongoDB ping failed on startup. Server may be offline; initializing in-memory fallback database for local web app demonstration..."
            )
            from mongomock_motor import AsyncMongoMockClient
            mock_client = AsyncMongoMockClient()
            mock_db = mock_client[settings.database_name]
            async_db_manager.set_mock_database(mock_db)
            await create_indexes(mock_db)
            from backend.scripts.create_admin import bootstrap_admin
            await bootstrap_admin(db=mock_db)

            # Seed initial sample cameras for prototype preview
            from backend.app.repositories.camera_repository import CameraRepository
            cam_repo = CameraRepository(db=mock_db)
            if await cam_repo.count() == 0:
                await cam_repo.create({
                    "camera_id": "CAM-001",
                    "name": "Main Gate Surveillance",
                    "location_name": "Gate 1 Surveillance Zone",
                    "zone": "Gate 1",
                    "latitude": 28.6139,
                    "longitude": 77.2090,
                    "stream_type": "FILE",
                    "rtsp_url": "storage/test_videos/cctv_sample.mp4",
                    "detection_mode": "BOTH",
                    "status": "ONLINE",
                    "is_active": True,
                })
                await cam_repo.create({
                    "camera_id": "CAM-002",
                    "name": "Central Plaza Walkway",
                    "location_name": "Plaza North Pathway",
                    "zone": "Plaza",
                    "latitude": 28.6145,
                    "longitude": 77.2095,
                    "stream_type": "WEBCAM",
                    "rtsp_url": "0",
                    "detection_mode": "SOLID",
                    "status": "ONLINE",
                    "is_active": True,
                })
    except Exception as e:
        logger.warning("Database initialization warning: %s", e)

    # 3. Configure WebSocket connection manager
    ws_manager = get_connection_manager()
    try:
        ws_manager.set_event_loop(asyncio.get_running_loop())
    except RuntimeError:
        pass

    if settings.WEBSOCKET_ENABLED:
        await ws_manager.start_heartbeat(settings.WEBSOCKET_HEARTBEAT_SECONDS)

    yield

    # Shutdown
    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    ws_manager.stop_heartbeat()
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


@app.websocket("/ws/alerts")
async def root_websocket_alerts_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """Direct root WebSocket endpoint /ws/alerts for authenticated real-time surveillance alerts."""
    await handle_websocket_alerts(websocket, token)

