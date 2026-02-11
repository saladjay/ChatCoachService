"""Screenshot processor service for analyzing chat screenshots.

This module previously integrated the screenshotanalysis library.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12
"""

import logging
from typing import Optional, List
from urllib.parse import urlparse

from app.models.v1_api import ImageResult
from app.core.v1_config import ScreenshotConfig


logger = logging.getLogger(__name__)


def is_url(content: str) -> bool:
    try:
        parsed = urlparse(content)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


class ModelUnavailableError(Exception):
    """Raised when screenshotanalysis models are not available."""
    pass


class ImageLoadError(Exception):
    """Raised when image loading fails."""
    pass


class InferenceError(Exception):
    """Raised when model inference fails."""
    pass


class ScreenshotProcessor:
    """Compatibility stub for the previous screenshotanalysis-based processor."""

    def __init__(self, config: ScreenshotConfig):
        """Initialize the screenshot processor.

        Args:
            config: Screenshot processing configuration

        Requirements: 4.1
        """
        self.config = config

    def _load_models(self) -> None:
        raise ModelUnavailableError(
            "screenshotanalysis support has been removed; use ScreenshotParserService instead"
        )

    async def process_screenshot(
        self,
        image_url: str,
        app_type: str,
        conf_threshold: Optional[float] = None
    ) -> ImageResult:
        raise ModelUnavailableError(
            "screenshotanalysis support has been removed; use ScreenshotParserService instead"
        )

    def _normalize_coordinates(
        self,
        box,
        padding: List[float],
        image_size: List[int],
    ) -> List[float]:
        """Normalize pixel coordinates to percentages (0.0-1.0).
        
        Args:
            box: Text box with pixel coordinates
            padding: Image padding [top, right, bottom, left]
            image_size: Image size [width, height]
            
        Returns:
            Normalized coordinates [min_x, min_y, max_x, max_y] in range 0.0-1.0
            
        Requirements: 4.8
        """
        # Get image dimensions
        width, height = image_size
        
        # Adjust for padding
        pad_top, pad_right, pad_bottom, pad_left = padding
        effective_width = width - pad_left - pad_right
        effective_height = height - pad_top - pad_bottom
        
        # Get box coordinates
        x_min = box.x_min - pad_left
        y_min = box.y_min - pad_top
        x_max = box.x_max - pad_left
        y_max = box.y_max - pad_top
        
        # Normalize to 0.0-1.0 range
        norm_x_min = max(0.0, min(1.0, x_min / effective_width))
        norm_y_min = max(0.0, min(1.0, y_min / effective_height))
        norm_x_max = max(0.0, min(1.0, x_max / effective_width))
        norm_y_max = max(0.0, min(1.0, y_max / effective_height))
        
        return [norm_x_min, norm_y_min, norm_x_max, norm_y_max]
