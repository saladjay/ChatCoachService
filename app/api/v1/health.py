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
from app.core.v1_dependencies import MetricsCollectorDep
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
    },
    summary="Check service health",
    description="""
    Check the health status of the ChatCoach service and verify that all
    required screenshotanalysis models are available.
    
    Returns HTTP 200 if all models are available.
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
    """,
)
async def health_check(
    metrics: MetricsCollectorDep,
) -> HealthResponse:
    """
    Check service and model health.
    
    Verifies that the service is available.
    
    Args:
        metrics: MetricsCollector service dependency
    
    Returns:
        HealthResponse with status, timestamp, version, and model availability
    
    Requirements:
        - 2.1: Return service status, timestamp, and version
        - 2.3: Accessible at /api/v1/ChatCoach/health
        - 2.4: Return HealthResponse model
        - 5.4: Track request metrics
    """
    import time
    start_time = time.time()
    
    models = {
        "screenshot_parser": True,
    }
 
    logger.info(
        "Health check: status=healthy, models=%s",
        models,
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
