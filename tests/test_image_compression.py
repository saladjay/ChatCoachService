"""
Test image compression functionality in ImageFetcher.

This test verifies that images are properly compressed when they exceed
the maximum dimension while maintaining aspect ratio.
"""

import io
import pytest
from PIL import Image

from app.services.image_fetcher import ImageFetcher


class TestImageCompression:
    """Test suite for image compression functionality."""

    def test_compress_large_image_width_longer(self):
        """Test compression when width is the longer dimension."""
        fetcher = ImageFetcher(max_dimension=800)
        
        # Create a large image (1200x800)
        img = Image.new('RGB', (1200, 800), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        original_bytes = img_bytes.getvalue()
        
        # Compress
        compressed_bytes, new_width, new_height = fetcher._compress_image_if_needed(
            original_bytes, 1200, 800
        )
        
        # Verify dimensions
        assert new_width == 800, f"Expected width 800, got {new_width}"
        assert new_height == 533, f"Expected height ~533, got {new_height}"  # 800 * (800/1200) ≈ 533
        
        # Verify compression occurred
        assert len(compressed_bytes) < len(original_bytes), "Image should be compressed"
        
        # Verify image is still valid
        compressed_img = Image.open(io.BytesIO(compressed_bytes))
        assert compressed_img.size == (new_width, new_height)

    def test_compress_large_image_height_longer(self):
        """Test compression when height is the longer dimension."""
        fetcher = ImageFetcher(max_dimension=800)
        
        # Create a large image (600x1200)
        img = Image.new('RGB', (600, 1200), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        original_bytes = img_bytes.getvalue()
        
        # Compress
        compressed_bytes, new_width, new_height = fetcher._compress_image_if_needed(
            original_bytes, 600, 1200
        )
        
        # Verify dimensions
        assert new_height == 800, f"Expected height 800, got {new_height}"
        assert new_width == 400, f"Expected width 400, got {new_width}"  # 800 * (600/1200) = 400
        
        # Verify compression occurred
        assert len(compressed_bytes) < len(original_bytes), "Image should be compressed"

    def test_no_compression_for_small_image(self):
        """Test that small images are not compressed."""
        fetcher = ImageFetcher(max_dimension=800)
        
        # Create a small image (400x300)
        img = Image.new('RGB', (400, 300), color='green')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        original_bytes = img_bytes.getvalue()
        
        # Try to compress
        result_bytes, new_width, new_height = fetcher._compress_image_if_needed(
            original_bytes, 400, 300
        )
        
        # Verify no compression
        assert new_width == 400, "Width should remain unchanged"
        assert new_height == 300, "Height should remain unchanged"
        assert result_bytes == original_bytes, "Bytes should be unchanged"

    def test_compress_exactly_max_dimension(self):
        """Test image with dimension exactly at max_dimension."""
        fetcher = ImageFetcher(max_dimension=800)
        
        # Create an image exactly at max dimension (800x600)
        img = Image.new('RGB', (800, 600), color='yellow')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        original_bytes = img_bytes.getvalue()
        
        # Try to compress
        result_bytes, new_width, new_height = fetcher._compress_image_if_needed(
            original_bytes, 800, 600
        )
        
        # Verify no compression (exactly at limit)
        assert new_width == 800, "Width should remain unchanged"
        assert new_height == 600, "Height should remain unchanged"
        assert result_bytes == original_bytes, "Bytes should be unchanged"

    def test_compress_rgba_image(self):
        """Test compression of RGBA image (with transparency)."""
        fetcher = ImageFetcher(max_dimension=800)
        
        # Create a large RGBA image (1000x800)
        img = Image.new('RGBA', (1000, 800), color=(255, 0, 0, 128))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        original_bytes = img_bytes.getvalue()
        
        # Compress
        compressed_bytes, new_width, new_height = fetcher._compress_image_if_needed(
            original_bytes, 1000, 800
        )
        
        # Verify dimensions
        assert new_width == 800, f"Expected width 800, got {new_width}"
        assert new_height == 640, f"Expected height 640, got {new_height}"
        
        # Verify image is valid (should be converted to RGB/JPEG)
        compressed_img = Image.open(io.BytesIO(compressed_bytes))
        assert compressed_img.size == (new_width, new_height)
        assert compressed_img.format == 'JPEG', "Should be converted to JPEG"

    def test_aspect_ratio_maintained(self):
        """Test that aspect ratio is maintained during compression."""
        fetcher = ImageFetcher(max_dimension=800)
        
        # Test various aspect ratios
        test_cases = [
            (1600, 900),   # 16:9
            (1200, 1200),  # 1:1
            (900, 1600),   # 9:16
            (2000, 1000),  # 2:1
        ]
        
        for orig_width, orig_height in test_cases:
            img = Image.new('RGB', (orig_width, orig_height), color='purple')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG')
            original_bytes = img_bytes.getvalue()
            
            compressed_bytes, new_width, new_height = fetcher._compress_image_if_needed(
                original_bytes, orig_width, orig_height
            )
            
            # Calculate aspect ratios
            original_ratio = orig_width / orig_height
            new_ratio = new_width / new_height
            
            # Allow small floating point difference
            assert abs(original_ratio - new_ratio) < 0.01, \
                f"Aspect ratio changed: {original_ratio:.3f} -> {new_ratio:.3f}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
