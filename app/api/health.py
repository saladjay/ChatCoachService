"""
Health check API endpoints.
Provides system health status and readiness checks.
"""

from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.core.dependencies import PersistenceServiceDep


# 尝试导入 screenshotanalysis 库
SCREENSHOT_ANALYSIS_AVAILABLE = False
SCREENSHOT_ANALYSIS_ERROR = None

try:
    import screenshotanalysis
    SCREENSHOT_ANALYSIS_AVAILABLE = True
except Exception as e:
    SCREENSHOT_ANALYSIS_ERROR = str(e)


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
        "dependencies": {
            "screenshotanalysis": {
                "available": SCREENSHOT_ANALYSIS_AVAILABLE,
            }
        }
    }
    
    # 如果有导入错误，添加错误信息
    if not SCREENSHOT_ANALYSIS_AVAILABLE and SCREENSHOT_ANALYSIS_ERROR:
        response["dependencies"]["screenshotanalysis"]["error"] = SCREENSHOT_ANALYSIS_ERROR
    
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
        "screenshotanalysis": "healthy" if SCREENSHOT_ANALYSIS_AVAILABLE else "unavailable",
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
    
    # 添加 screenshotanalysis 错误详情
    if not SCREENSHOT_ANALYSIS_AVAILABLE and SCREENSHOT_ANALYSIS_ERROR:
        response["screenshotanalysis_error"] = SCREENSHOT_ANALYSIS_ERROR
    
    return response
