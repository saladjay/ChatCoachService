"""
Metrics endpoint for ChatCoach API v1.

This module provides the GET /api/v1/ChatCoach/metrics endpoint that exposes
performance metrics in Prometheus text format.

Requirements: 5.1, 5.2, 5.3
"""

import logging

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.v1_dependencies import MetricsCollectorDep


logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    responses={
        200: {
            "description": "Prometheus-formatted metrics",
            "content": {
                "text/plain": {
                    "example": """# HELP chatcoach_requests_total Total number of requests by endpoint
# TYPE chatcoach_requests_total counter
chatcoach_requests_total{endpoint="health"} 100
chatcoach_requests_total{endpoint="predict"} 250
chatcoach_requests_total{endpoint="metrics"} 10"""
                }
            },
        },
    },
    summary="Get performance metrics",
    description="""
    Retrieve performance metrics in Prometheus text format.
    
    Metrics include:
    - Request counts by endpoint
    - Success/error counts
    - Request latencies (average and p95)
    - Screenshot processing times
    - Reply generation times
    - Error rate
    
    Requirements: 5.1, 5.2, 5.3
    """,
)
async def get_metrics(
    metrics_collector: MetricsCollectorDep,
) -> str:
    """
    Return Prometheus format metrics.
    
    Exposes performance metrics for monitoring and alerting. The metrics
    are formatted according to the Prometheus text exposition format.
    
    Args:
        metrics_collector: MetricsCollector service dependency
    
    Returns:
        Prometheus-formatted metrics as plain text
    
    Requirements:
        - 5.1: Return Prometheus-compatible metrics
        - 5.2: Accessible at /api/v1/ChatCoach/metrics
        - 5.3: Return metrics in plain text format
        - 5.4: Track request counts, latencies, and error rates
    """
    import time
    start_time = time.time()
    
    logger.debug("Metrics endpoint called")
    
    # Get Prometheus-formatted metrics
    prometheus_metrics = metrics_collector.get_prometheus_metrics()
    
    # Track metrics request
    duration_ms = int((time.time() - start_time) * 1000)
    metrics_collector.record_request("metrics", 200, duration_ms)
    
    logger.debug(f"Returning {len(prometheus_metrics)} bytes of metrics")
    
    return prometheus_metrics
