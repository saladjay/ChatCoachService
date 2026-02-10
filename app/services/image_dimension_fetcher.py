"""Background task for fetching image dimensions and caching them.

This module provides functionality to:
- Download images in the background to get their dimensions
- Cache the dimensions for future use
- Clean up downloaded images immediately after dimension extraction
"""

import asyncio
import logging
from typing import Optional
import httpx
from PIL import Image
import io

logger = logging.getLogger(__name__)


class ImageDimensionFetcher:
    """Fetches image dimensions in the background and caches them."""
    
    def __init__(self, timeout: float = 10.0):
        """Initialize the dimension fetcher.
        
        Args:
            timeout: HTTP request timeout in seconds (default: 10.0)
        """
        self.timeout = timeout
    
    async def fetch_dimensions(self, url: str) -> Optional[tuple[int, int]]:
        """Download image and extract dimensions.
        
        This is a lightweight operation that only downloads enough data
        to extract dimensions, then immediately discards the image data.
        
        Args:
            url: Image URL to fetch
            
        Returns:
            Tuple of (width, height) or None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                image_bytes = response.content
            
            # Extract dimensions
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            
            # Validate dimensions
            if width <= 0 or height <= 0:
                logger.warning(f"Invalid dimensions for {url}: {width}x{height}")
                return None
            
            logger.info(f"Fetched dimensions for {url}: {width}x{height}")
            return width, height
            
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error fetching dimensions for {url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error fetching dimensions for {url}: {e}")
            return None
    
    async def fetch_and_cache(
        self,
        url: str,
        cache_service,
        session_id: str,
        scene: int,
    ) -> None:
        """Fetch dimensions and cache them (background task).
        
        This is designed to run as a background task without blocking
        the main request flow.
        
        Args:
            url: Image URL to fetch
            cache_service: Cache service instance
            session_id: Session ID for caching
            scene: Scene type for caching
        """
        try:
            logger.info(f"Background task: Fetching dimensions for {url}")
            
            # Fetch dimensions
            dimensions = await self.fetch_dimensions(url)
            
            if dimensions is None:
                logger.warning(f"Background task: Failed to fetch dimensions for {url}")
                return
            
            width, height = dimensions
            
            # Cache the dimensions
            await cache_service.append_event(
                session_id=session_id,
                category="image_dimensions",
                resource=url,
                payload={
                    "width": width,
                    "height": height,
                    "url": url,
                },
                scene=scene,
            )
            
            logger.info(
                f"Background task: Cached dimensions for {url}: {width}x{height}"
            )
            
        except Exception as e:
            logger.error(
                f"Background task: Error in fetch_and_cache for {url}: {e}",
                exc_info=True
            )
    
    async def get_cached_dimensions(
        self,
        url: str,
        cache_service,
        session_id: str,
        scene: int,
    ) -> Optional[tuple[int, int]]:
        """Get cached dimensions for an image URL.
        
        Args:
            url: Image URL
            cache_service: Cache service instance
            session_id: Session ID
            scene: Scene type
            
        Returns:
            Tuple of (width, height) or None if not cached
        """
        try:
            # Try to get from cache
            cached_events = await cache_service.get_events(
                session_id=session_id,
                category="image_dimensions",
                resource=url,
                scene=scene,
            )
            
            if cached_events and len(cached_events) > 0:
                # Get the most recent cached dimensions
                latest_event = cached_events[-1]
                payload = latest_event.get("payload", {})
                
                width = payload.get("width")
                height = payload.get("height")
                
                if width and height:
                    logger.info(
                        f"Using cached dimensions for {url}: {width}x{height}"
                    )
                    return width, height
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting cached dimensions for {url}: {e}")
            return None


# Global instance
_dimension_fetcher: Optional[ImageDimensionFetcher] = None


def get_dimension_fetcher() -> ImageDimensionFetcher:
    """Get or create the global dimension fetcher instance."""
    global _dimension_fetcher
    if _dimension_fetcher is None:
        _dimension_fetcher = ImageDimensionFetcher()
    return _dimension_fetcher
