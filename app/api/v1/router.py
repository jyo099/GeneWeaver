"""
GeneWeaver API v1 Router.

Centralizes registration of version 1 API endpoints.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health

api_router = APIRouter()

# Register health endpoints
api_router.include_router(
    health.router,
    tags=["Health"],
)
