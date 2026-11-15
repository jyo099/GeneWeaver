
"""
GeneWeaver Health Endpoint.

Provides application health information.
"""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get(
    "/health",
    summary="Check application health",
    description="Returns the operational status of GeneWeaver.",
    response_description="Application health information",
)
async def health_check(request: Request) -> dict:
    """Return basic application health information."""

    settings = request.app.state.settings

    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }




