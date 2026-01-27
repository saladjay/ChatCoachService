"""Image fetcher component for downloading and processing screenshot images.

This module provides the ImageFetcher class that handles:
- URL validation
- Image downloading via HTTP
- Dimension extraction
- Format validation
- Base64 conversion for LLM APIs
"""

import base64
import io
from urllib.parse import urlparse

import httpx
from PIL import Image

from app.models.screenshot import FetchedImage


class ImageFetcher:
    """Component for downloading and processing images from URLs.
    
    This component handles all image-related operations including validation,
    downloading, dimension extraction, and format conversion.
    """

    def __init__(self, timeout: float = 30.0):
        """Initialize ImageFetcher with configurable timeout.
        
        Args:
            timeout: HTTP request timeout in seconds (default: 30.0)
        """
        self.timeout = timeout

    async def fetch_image(self, url: str) -> FetchedImage:
        """Download and process an image from a URL.
        
        Args:
            url: Public URL of the image to fetch
            
        Returns:
            FetchedImage containing processed image data
            
        Raises:
            ValueError: If URL is invalid or image cannot be processed
        """
        # Validate URL format
        self._validate_url(url)
        
        # Download image
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                image_bytes = response.content
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to download image from URL: {e}")
        except Exception as e:
            raise ValueError(f"Unexpected error downloading image: {e}")
        
        # Extract dimensions and validate format
        width, height = self._extract_dimensions(image_bytes)
        
        # Determine image format
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img_format = img.format.lower() if img.format else "unknown"
        except Exception:
            img_format = "unknown"
        
        # Convert to base64
        base64_data = self._convert_to_base64(image_bytes)
        
        return FetchedImage(
            url=url,
            width=width,
            height=height,
            base64_data=base64_data,
            format=img_format
        )

    def _validate_url(self, url: str) -> None:
        """Validate URL format and accessibility.
        
        Args:
            url: URL to validate
            
        Raises:
            ValueError: If URL format is invalid
        """
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")
        
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")
        
        # Check that scheme is HTTP or HTTPS
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL must use HTTP or HTTPS protocol, got: {parsed.scheme}")
        
        # Check that netloc (domain) is present
        if not parsed.netloc:
            raise ValueError("URL must include a domain name")

    def _extract_dimensions(self, image_bytes: bytes) -> tuple[int, int]:
        """Extract image width and height.
        
        Args:
            image_bytes: Raw image data
            
        Returns:
            Tuple of (width, height) in pixels
            
        Raises:
            ValueError: If image format is invalid
        """
        if not image_bytes:
            raise ValueError("Image data is empty")
        
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            
            # Validate that dimensions are positive
            if width <= 0 or height <= 0:
                raise ValueError(f"Invalid image dimensions: {width}x{height}")
            
            # Validate image format
            if img.format not in ("PNG", "JPEG", "WEBP"):
                raise ValueError(
                    f"Unsupported image format: {img.format}. "
                    "Supported formats: PNG, JPEG, WebP"
                )
            
            return width, height
            
        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            raise ValueError(f"Failed to extract image dimensions: {e}")

    def _convert_to_base64(self, image_bytes: bytes) -> str:
        """Convert image bytes to base64 string for LLM API.
        
        Args:
            image_bytes: Raw image data
            
        Returns:
            Base64-encoded string
        """
        if not image_bytes:
            raise ValueError("Image data is empty")
        
        return base64.b64encode(image_bytes).decode("utf-8")
