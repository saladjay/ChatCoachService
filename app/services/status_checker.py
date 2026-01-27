"""Status checker service for monitoring model availability and service health.

This module provides the StatusChecker class that verifies the availability
of screenshotanalysis models (text detection, layout detection, text recognition)
and returns aggregated health status.

Requirements: 2.1, 2.2, 2.5
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


# Try to import screenshotanalysis library and its models
SCREENSHOT_ANALYSIS_AVAILABLE = False
SCREENSHOT_ANALYSIS_ERROR = None
TEXT_DET_AVAILABLE = False
LAYOUT_DET_AVAILABLE = False
TEXT_REC_AVAILABLE = False

try:
    import screenshotanalysis as AnalysisCore
    SCREENSHOT_ANALYSIS_AVAILABLE = True
    
    # Check if individual model modules are available
    try:
        TextObjDet = AnalysisCore.text_det
        TEXT_DET_AVAILABLE = True
    except (AttributeError, ImportError) as e:
        logger.warning(f"Text detection model not available: {e}")
    
    try:
        DocLayoutDet = AnalysisCore.layout_det
        LAYOUT_DET_AVAILABLE = True
    except (AttributeError, ImportError) as e:
        logger.warning(f"Layout detection model not available: {e}")
    
    try:
        EnTextRec = AnalysisCore.en_rec
        TEXT_REC_AVAILABLE = True
    except (AttributeError, ImportError) as e:
        logger.warning(f"Text recognition model not available: {e}")
        
except ImportError as e:
    SCREENSHOT_ANALYSIS_ERROR = str(e)
    logger.error(f"Failed to import screenshotanalysis: {e}")
except Exception as e:
    SCREENSHOT_ANALYSIS_ERROR = str(e)
    logger.error(f"Unexpected error importing screenshotanalysis: {e}")


class StatusChecker:
    """Service for checking model availability and service health.
    
    This service verifies that the screenshotanalysis library and its
    required models (text detection, layout detection, text recognition)
    are properly loaded and available for use.
    
    Requirements: 2.1, 2.2, 2.5
    """
    
    def __init__(self):
        """Initialize the status checker.
        
        The status checker uses module-level flags to determine model
        availability, which are set during import time.
        """
        self._screenshot_analysis_available = SCREENSHOT_ANALYSIS_AVAILABLE
        self._screenshot_analysis_error = SCREENSHOT_ANALYSIS_ERROR
        self._text_det_available = TEXT_DET_AVAILABLE
        self._layout_det_available = LAYOUT_DET_AVAILABLE
        self._text_rec_available = TEXT_REC_AVAILABLE
    
    def check_models(self) -> Dict[str, bool]:
        """Check if screenshotanalysis models are loaded.
        
        Verifies the availability of:
        - Text detection model (text_det)
        - Layout detection model (layout_det)
        - Text recognition model (en_rec)
        
        Returns:
            Dictionary mapping model names to availability status:
            {
                "text_detection": bool,
                "layout_detection": bool,
                "text_recognition": bool,
                "screenshotanalysis": bool
            }
        
        Requirements: 2.5
        """
        return {
            "text_detection": self._text_det_available,
            "layout_detection": self._layout_det_available,
            "text_recognition": self._text_rec_available,
            "screenshotanalysis": self._screenshot_analysis_available,
        }
    
    def is_healthy(self) -> bool:
        """Check overall service health.
        
        The service is considered healthy if:
        - The screenshotanalysis library is available
        - All required models (text detection, layout detection, text recognition) are available
        
        Returns:
            True if all models are available, False otherwise
        
        Requirements: 2.1, 2.2
        """
        return (
            self._screenshot_analysis_available
            and self._text_det_available
            and self._layout_det_available
            and self._text_rec_available
        )
    
    def get_error_message(self) -> str | None:
        """Get error message if models are unavailable.
        
        Returns:
            Error message string if screenshotanalysis failed to import,
            None if everything is available
        """
        if not self._screenshot_analysis_available:
            return self._screenshot_analysis_error
        
        # Check for individual model failures
        missing_models = []
        if not self._text_det_available:
            missing_models.append("text_detection")
        if not self._layout_det_available:
            missing_models.append("layout_detection")
        if not self._text_rec_available:
            missing_models.append("text_recognition")
        
        if missing_models:
            return f"Missing models: {', '.join(missing_models)}"
        
        return None
