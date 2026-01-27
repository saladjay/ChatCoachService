"""
Health check endpoint for ChatCoach API v1.

This module provides the GET /api/v1/ChatCoach/health endpoint that checks
service availability and model status.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.models.v1_api import HealthResponse, ErrorResponse
from app.core.v1_dependencies import StatusCheckerDep, MetricsCollectorDep
from app.core.config import settings


logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "",
    response_model=HealthResponse,
    responses={
        200: {
            "description": "Service is healthy and all models are available",
            "model": HealthResponse,
        },
        401: {
            "description": "Service is unhealthy - models are unavailable",
            "model": ErrorResponse,
        },
    },
    summary="Check service health",
    description="""
    Check the health status of the ChatCoach service and verify that all
    required screenshotanalysis models are available.
    
    Returns HTTP 200 if all models are available, HTTP 401 if any models
    are unavailable.
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
    """,
)
async def health_check(
    status_checker: StatusCheckerDep,
    metrics: MetricsCollectorDep,
) -> HealthResponse:
    """
    Check service and model health.
    
    Verifies that the screenshotanalysis library and all required models
    (text detection, layout detection, text recognition) are properly loaded
    and available for use.
    
    Args:
        status_checker: StatusChecker service dependency
        metrics: MetricsCollector service dependency
    
    Returns:
        HealthResponse with status, timestamp, version, and model availability
    
    Raises:
        HTTPException: 401 if models are unavailable
    
    Requirements:
        - 2.1: Return service status, timestamp, and version
        - 2.2: Return HTTP 401 if models unavailable
        - 2.3: Accessible at /api/v1/ChatCoach/health
        - 2.4: Return HealthResponse model
        - 2.5: Check text detection, layout detection, text recognition models
        - 5.4: Track request metrics
    """
    import time
    start_time = time.time()
    
    # Check model availability
    models = status_checker.check_models()
    is_healthy = status_checker.is_healthy()
    
    # Log health check
    logger.info(
        f"Health check: status={'healthy' if is_healthy else 'unhealthy'}, "
        f"models={models}"
    )
    
    # If models are unavailable, return HTTP 401
    if not is_healthy:
        error_message = status_checker.get_error_message()
        logger.error(f"Health check failed: {error_message}")
        
        # Track failed request
        duration_ms = int((time.time() - start_time) * 1000)
        metrics.record_request("health", 401, duration_ms)
        
        raise HTTPException(
            status_code=401,
            detail=error_message or "Model Unavailable",
        )
    
    # Track successful request
    duration_ms = int((time.time() - start_time) * 1000)
    metrics.record_request("health", 200, duration_ms)
    
    # Return healthy response
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version=settings.app_version,
        models=models,
    )
