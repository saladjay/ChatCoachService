"""FastAPI dependency injection for ChatCoach API v1.

This module provides dependency injection functions for v1 API endpoints,
managing service instances for StatusChecker, ScreenshotProcessor, and
MetricsCollector. It also handles initialization of screenshotanalysis models.

Requirements: 4.1
"""

import logging
from typing import Annotated

from fastapi import Depends

from app.core.v1_config import get_v1_config, V1Config
from app.services.status_checker import StatusChecker
from app.services.screenshot_processor import ScreenshotProcessor
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


# Try to import screenshotanalysis
SCREENSHOT_ANALYSIS_AVAILABLE = False
try:
    from screenshotanalysis.dialog_pipeline2 import analyze_chat_image
    from screenshotanalysis import ChatLayoutAnalyzer, ChatTextRecognition
    from screenshotanalysis.processors import ChatMessageProcessor
    SCREENSHOT_ANALYSIS_AVAILABLE = True
    logger.info("screenshotanalysis library imported successfully")
except ImportError as e:
    logger.error(f"Failed to import screenshotanalysis: {e}")
    analyze_chat_image = None
    ChatLayoutAnalyzer = None
    ChatTextRecognition = None
    ChatMessageProcessor = None


class ScreenshotAnalysisService:
    """Service wrapper for screenshotanalysis library using analyze_chat_image."""
    
    def __init__(self):
        """Initialize the service with lazy-loaded models."""
        self._text_det_analyzer = None
        self._layout_det_analyzer = None
        self._text_rec = None
        self._processor = None
        self._models_loaded = False
    
    def _ensure_models_loaded(self):
        """Lazy load models on first use."""
        if self._models_loaded:
            return
        
        if not SCREENSHOT_ANALYSIS_AVAILABLE:
            raise Exception("screenshotanalysis library is not available")
        
        logger.info("Loading screenshotanalysis models...")
        self._text_det_analyzer = ChatLayoutAnalyzer(model_name="PP-OCRv5_server_det")
        self._text_det_analyzer.load_model()
        
        self._layout_det_analyzer = ChatLayoutAnalyzer(model_name="PP-DocLayoutV2")
        self._layout_det_analyzer.load_model()
        
        self._text_rec = ChatTextRecognition(model_name="PP-OCRv5_server_rec", lang="en")
        self._text_rec.load_model()
        
        self._processor = ChatMessageProcessor()
        self._models_loaded = True
        logger.info("All screenshotanalysis models loaded successfully")
    
    async def analyze_screenshot(self, image_path: str) -> dict:
        """
        Analyze a screenshot using analyze_chat_image.
        
        Args:
            image_path: Path or URL to the screenshot image
            
        Returns:
            Dictionary with talker_nickname, dialogs, and timings
        """
        self._ensure_models_loaded()
        
        # Call analyze_chat_image with loaded models
        output_payload, _ = analyze_chat_image(
            image_path=image_path,
            output_path=None,
            draw_output_path=None,
            text_det_analyzer=self._text_det_analyzer,
            layout_det_analyzer=self._layout_det_analyzer,
            text_rec=self._text_rec,
            processor=self._processor,
            speaker_map={"A": "other", "B": "self", None: "self"},
            track_model_calls=False,
        )
        
        return output_payload


# Global service instances (singleton pattern)
_status_checker: StatusChecker | None = None
_screenshot_processor: ScreenshotProcessor | None = None
_screenshot_analysis_service: ScreenshotAnalysisService | None = None
_metrics_collector: MetricsCollector | None = None


def get_v1_status_checker() -> StatusChecker:
    """Get the StatusChecker service dependency.
    
    Creates a singleton StatusChecker instance that checks the availability
    of screenshotanalysis models (text detection, layout detection, text
    recognition).
    
    Returns:
        StatusChecker instance for checking model availability
        
    Requirements: 4.1
    """
    global _status_checker
    
    if _status_checker is None:
        logger.info("Initializing StatusChecker service")
        _status_checker = StatusChecker()
        
        # Log initial model status
        models = _status_checker.check_models()
        is_healthy = _status_checker.is_healthy()
        logger.info(
            f"StatusChecker initialized: healthy={is_healthy}, models={models}"
        )
        
        if not is_healthy:
            error_msg = _status_checker.get_error_message()
            logger.warning(f"Models not fully available: {error_msg}")
    
    return _status_checker


def get_v1_screenshot_processor() -> ScreenshotProcessor:
    """Get the ScreenshotProcessor service dependency.
    
    Creates a singleton ScreenshotProcessor instance configured with
    v1 screenshot settings. The processor handles:
    - Lazy loading of screenshotanalysis models
    - Image loading from URLs
    - Text and layout detection
    - Text extraction using OCR
    - Speaker identification
    - Coordinate normalization
    - Message grouping
    
    Returns:
        ScreenshotProcessor instance for analyzing screenshots
        
    Requirements: 4.1
    """
    global _screenshot_processor
    
    if _screenshot_processor is None:
        logger.info("Initializing ScreenshotProcessor service")
        config = get_v1_config()
        _screenshot_processor = ScreenshotProcessor(config.screenshot)
        logger.info(
            f"ScreenshotProcessor initialized with config: "
            f"languages={config.screenshot.supported_languages}, "
            f"threshold={config.screenshot.default_conf_threshold}"
        )
    
    return _screenshot_processor


def get_v1_screenshot_analysis_service() -> ScreenshotAnalysisService:
    """Get the ScreenshotAnalysisService dependency.
    
    Creates a singleton ScreenshotAnalysisService instance that uses
    analyze_chat_image from dialog_pipeline2 for screenshot processing.
    
    Returns:
        ScreenshotAnalysisService instance for analyzing screenshots
        
    Requirements: 4.1
    """
    global _screenshot_analysis_service
    
    if _screenshot_analysis_service is None:
        logger.info("Initializing ScreenshotAnalysisService")
        _screenshot_analysis_service = ScreenshotAnalysisService()
        logger.info("ScreenshotAnalysisService initialized")
    
    return _screenshot_analysis_service


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
StatusCheckerDep = Annotated[StatusChecker, Depends(get_v1_status_checker)]
ScreenshotProcessorDep = Annotated[ScreenshotProcessor, Depends(get_v1_screenshot_processor)]
ScreenshotAnalysisServiceDep = Annotated[ScreenshotAnalysisService, Depends(get_v1_screenshot_analysis_service)]
MetricsCollectorDep = Annotated[MetricsCollector, Depends(get_v1_metrics_collector)]
OrchestratorDep = Annotated[Orchestrator, Depends(get_v1_orchestrator)]


def reset_v1_dependencies() -> None:
    """Reset all v1 service instances.
    
    This function is primarily used for testing to ensure a clean state
    between test runs. It clears all singleton instances, forcing them
    to be recreated on next access.
    """
    global _status_checker, _screenshot_processor, _screenshot_analysis_service, _metrics_collector
    
    logger.info("Resetting v1 dependencies")
    _status_checker = None
    _screenshot_processor = None
    _screenshot_analysis_service = None
    _metrics_collector = None
