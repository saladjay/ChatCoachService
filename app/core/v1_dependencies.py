"""FastAPI dependency injection for ChatCoach API v1.

This module provides dependency injection functions for v1 API endpoints,
managing service instances for MetricsCollector and Orchestrator.

Requirements: 4.1
"""

import logging
from typing import Annotated

from fastapi import Depends

from app.services.metrics_collector import MetricsCollector, metrics
from app.services.orchestrator import Orchestrator
from app.services.persistence import PersistenceService
from app.core.dependencies import (
    get_orchestrator,
    get_service_container,
    get_persistence_service,
)
from app.core.container import ServiceContainer

logger = logging.getLogger(__name__)

# Global service instances (singleton pattern)
_metrics_collector: MetricsCollector | None = None


def get_v1_metrics_collector() -> MetricsCollector:
    """Get the MetricsCollector service dependency.
    
    Returns the global MetricsCollector instance that tracks:
    - Request counts by endpoint
    - Response times and latencies
    - Error rates
    - Screenshot processing times
    - Reply generation times
    
    The metrics are formatted as Prometheus-compatible text format.
    
    Returns:
        MetricsCollector instance for tracking performance metrics
        
    Requirements: 4.1
    """
    # Use the global metrics instance from metrics_collector module
    # This ensures all endpoints share the same metrics collector
    return metrics


def get_v1_orchestrator(
    container: Annotated[ServiceContainer, Depends(get_service_container)],
    persistence_service: Annotated[PersistenceService, Depends(get_persistence_service)],
) -> Orchestrator:
    """Get the Orchestrator service dependency for reply generation.
    
    Returns the Orchestrator instance from the main service container,
    which handles the complete reply generation workflow including:
    - Context building
    - Scene analysis
    - Persona inference
    - Reply generation
    - Intimacy checking
    
    Args:
        container: Service container dependency
        persistence_service: Persistence service dependency
    
    Returns:
        Orchestrator instance for generating reply suggestions
        
    Requirements: 4.1
    """
    # Reuse the existing orchestrator dependency from main app
    # This ensures consistency with the rest of the application
    return get_orchestrator(container, persistence_service)


# Type aliases for cleaner route signatures
MetricsCollectorDep = Annotated[MetricsCollector, Depends(get_v1_metrics_collector)]
OrchestratorDep = Annotated[Orchestrator, Depends(get_v1_orchestrator)]


def reset_v1_dependencies() -> None:
    """Reset all v1 service instances.
    
    This function is primarily used for testing to ensure a clean state
    between test runs. It clears all singleton instances, forcing them
    to be recreated on next access.
    """
    global _metrics_collector
    
    logger.info("Resetting v1 dependencies")
    _metrics_collector = None
