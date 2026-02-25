"""API v1 router combining all endpoints."""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.cases import router as cases_router
from app.api.v1.devices import router as devices_router
from app.api.v1.flows import router as flows_router
from app.api.v1.projects import router as projects_router
from app.api.v1.reports import router as reports_router
from app.api.v1.runs import router as runs_router
from app.api.v1.websocket import router as ws_router
from app.api.v1.assets import router as assets_router
from app.api.v1.packages import router as packages_router

api_router = APIRouter()

# Include all routers
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(devices_router)
api_router.include_router(cases_router)
api_router.include_router(flows_router)
api_router.include_router(runs_router)
api_router.include_router(reports_router)
api_router.include_router(assets_router)
api_router.include_router(packages_router)

# WebSocket routes (no prefix)
api_router.include_router(ws_router, tags=["WebSocket"])
