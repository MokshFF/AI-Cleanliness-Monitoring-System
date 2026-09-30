"""Consolidated API v1 Router."""
from fastapi import APIRouter
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.users import router as users_router
from backend.app.api.v1.cameras import router as cameras_router
from backend.app.api.v1.incidents import router as incidents_router
from backend.app.api.v1.websocket import router as websocket_router
from backend.app.api.v1.map import router as map_router
from backend.app.api.v1.analytics import router as analytics_router
from backend.app.api.v1.reports import router as reports_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(cameras_router)
api_router.include_router(incidents_router)
api_router.include_router(websocket_router)
api_router.include_router(map_router)
api_router.include_router(analytics_router)
api_router.include_router(reports_router)

