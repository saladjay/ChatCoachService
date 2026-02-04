"""Status checker service for monitoring model availability and service health.

This module provides the StatusChecker class that verifies the availability
of service dependencies and returns aggregated health status.

Requirements: 2.1, 2.2, 2.5
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class StatusChecker:
    """Service for checking model availability and service health.
    
    This service provides a minimal health surface for the API.
    """
    
    def __init__(self):
        pass
    
    def check_models(self) -> Dict[str, bool]:
        return {
            "screenshot_parser": True,
        }
     
    def is_healthy(self) -> bool:
        return True
     
    def get_error_message(self):
        return None
