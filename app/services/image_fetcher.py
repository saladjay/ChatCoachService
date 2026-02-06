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

    def __init__(self, timeout: float = 30.0, max_dimension: int = 800):
        """Initialize ImageFetcher with configurable timeout and compression.
        
        Args:
            timeout: HTTP request timeout in seconds (default: 30.0)
            max_dimension: Maximum dimension (width or height) for image compression (default: 800)
        """
        self.timeout = timeout
        self.max_dimension = max_dimension

    async def fetch_image(self, url: str, compress: bool = True) -> FetchedImage:
        """Download and process an image from a URL.
        
        Args:
            url: Public URL of the image to fetch
            compress: Whether to compress the image (default: True)
                     Set to False when using URL format to avoid unnecessary processing
            
        Returns:
            FetchedImage containing processed image data (compressed if compress=True)
            
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
        original_width, original_height = self._extract_dimensions(image_bytes)
        
        # Determine image format
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img_format = img.format.lower() if img.format else "unknown"
        except Exception:
            img_format = "unknown"
        
        # Compress image if needed and requested
        if compress:
            compressed_bytes, final_width, final_height = self._compress_image_if_needed(
                image_bytes, original_width, original_height
            )
        else:
            # Skip compression when using URL format
            compressed_bytes = image_bytes
            final_width = original_width
            final_height = original_height
        
        # Convert to base64
        base64_data = self._convert_to_base64(compressed_bytes)
        
        return FetchedImage(
            url=url,
            width=final_width,
            height=final_height,
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
            if img.format not in ("PNG", "JPEG", "WEBP", "GIF", "BMP"):
                raise ValueError(
                    f"Unsupported image format: {img.format}. "
                    "Supported formats: PNG, JPEG, WebP, GIF, BMP"
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

    def _compress_image_if_needed(
        self, 
        image_bytes: bytes, 
        width: int, 
        height: int
    ) -> tuple[bytes, int, int]:
        """Compress image if dimensions exceed max_dimension, maintaining aspect ratio.
        
        Args:
            image_bytes: Original image data
            width: Original image width
            height: Original image height
            
        Returns:
            Tuple of (compressed_bytes, new_width, new_height)
        """
        # Check if compression is needed
        max_dim = max(width, height)
        if max_dim <= self.max_dimension:
            # No compression needed
            return image_bytes, width, height
        
        try:
            # Open image
            img = Image.open(io.BytesIO(image_bytes))
            
            # Calculate new dimensions maintaining aspect ratio
            if width > height:
                # Width is the longer side
                new_width = self.max_dimension
                new_height = int(height * (self.max_dimension / width))
            else:
                # Height is the longer side
                new_height = self.max_dimension
                new_width = int(width * (self.max_dimension / height))
            
            # Resize image with high-quality resampling
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert to bytes
            output = io.BytesIO()
            # Save as JPEG for better compression (convert RGBA to RGB if needed)
            if resized_img.mode in ('RGBA', 'LA', 'P'):
                # Convert to RGB for JPEG
                rgb_img = Image.new('RGB', resized_img.size, (255, 255, 255))
                if resized_img.mode == 'P':
                    resized_img = resized_img.convert('RGBA')
                rgb_img.paste(resized_img, mask=resized_img.split()[-1] if resized_img.mode in ('RGBA', 'LA') else None)
                resized_img = rgb_img
            
            # Save with good quality
            resized_img.save(output, format='JPEG', quality=85, optimize=True)
            compressed_bytes = output.getvalue()
            
            # Log compression info
            original_size = len(image_bytes) / 1024  # KB
            compressed_size = len(compressed_bytes) / 1024  # KB
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"Image compressed: {width}x{height} -> {new_width}x{new_height}, "
                f"Size: {original_size:.1f}KB -> {compressed_size:.1f}KB "
                f"({compression_ratio:.1f}% reduction)"
            )
            
            return compressed_bytes, new_width, new_height
            
        except Exception as e:
            # If compression fails, return original
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Image compression failed, using original: {e}")
            return image_bytes, width, height
