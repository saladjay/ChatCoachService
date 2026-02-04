"""
Health check API endpoints.
Provides system health status and readiness checks.
"""

from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.core.dependencies import PersistenceServiceDep


router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns:
        dict: Health status and application version
    """
    response = {
        "status": "healthy",
        "version": settings.app_version,
        "app_name": settings.app_name,
        "dependencies": {}
    }
    return response


@router.get("/ready")
async def readiness_check(
    persistence_service: PersistenceServiceDep,
) -> dict[str, Any]:
    """
    Readiness check endpoint.
    Verifies that the application and its dependencies are ready to serve requests.
    
    Returns:
        dict: Readiness status with dependency checks
    """
    checks = {
        "database": "unknown",
    }
    
    # Check database connectivity
    try:
        # Simple check to verify database is accessible
        await persistence_service.list_conversation_summaries(
            user_id="health_check",
            target_id="health_check",
            limit=1,
        )
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
    
    overall_status = "ready" if all(
        status == "healthy" for status in checks.values()
    ) else "not_ready"
    
    response = {
        "status": overall_status,
        "checks": checks,
        "version": settings.app_version,
    }
    return response
