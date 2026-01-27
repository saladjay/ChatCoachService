"""Property-based tests for coordinate normalization in Screenshot Processor.

This module contains property-based tests that verify the coordinate normalization
functionality ensures all coordinates are within valid bounds.

Feature: chatcoach-api-refactor
"""

import pytest
from hypothesis import given, strategies as st, assume
from app.services.screenshot_processor import ScreenshotProcessor
from app.core.v1_config import ScreenshotConfig


# Mock box class for testing
class MockBox:
    """Mock text box for testing coordinate normalization."""
    
    def __init__(self, x_min: float, y_min: float, x_max: float, y_max: float):
        self.x_min = x_min
        self.y_min = y_min
        self.x_max = x_max
        self.y_max = y_max


# Generators for test data
@st.composite
def valid_image_dimensions(draw):
    """Generate valid image dimensions."""
    width = draw(st.integers(min_value=100, max_value=5000))
    height = draw(st.integers(min_value=100, max_value=5000))
    return [width, height]


@st.composite
def valid_padding(draw, image_size):
    """Generate valid padding that doesn't exceed image dimensions."""
    width, height = image_size
    
    # Padding should be reasonable (not exceed half the dimension)
    pad_left = draw(st.integers(min_value=0, max_value=width // 4))
    pad_right = draw(st.integers(min_value=0, max_value=width // 4))
    pad_top = draw(st.integers(min_value=0, max_value=height // 4))
    pad_bottom = draw(st.integers(min_value=0, max_value=height // 4))
    
    # Ensure padding doesn't exceed image dimensions
    assume(pad_left + pad_right < width)
    assume(pad_top + pad_bottom < height)
    
    return [pad_top, pad_right, pad_bottom, pad_left]


@st.composite
def valid_box_coordinates(draw, image_size, padding):
    """Generate valid box coordinates within image bounds."""
    width, height = image_size
    pad_top, pad_right, pad_bottom, pad_left = padding
    
    # Calculate effective area (after padding)
    effective_width = width - pad_left - pad_right
    effective_height = height - pad_top - pad_bottom
    
    # Generate box coordinates within effective area
    x_min = draw(st.integers(min_value=pad_left, max_value=pad_left + effective_width - 10))
    y_min = draw(st.integers(min_value=pad_top, max_value=pad_top + effective_height - 10))
    
    # Ensure box has positive dimensions
    x_max = draw(st.integers(min_value=x_min + 1, max_value=min(x_min + 500, pad_left + effective_width)))
    y_max = draw(st.integers(min_value=y_min + 1, max_value=min(y_min + 500, pad_top + effective_height)))
    
    return MockBox(x_min, y_min, x_max, y_max)


# Feature: chatcoach-api-refactor, Property 9: Coordinate Normalization Bounds
@given(
    data=st.data(),
)
def test_property_9_coordinate_normalization_bounds(data):
    """Property 9: For any position coordinate in a dialog item, all four values
    (min_x, min_y, max_x, max_y) should satisfy: 0.0 ≤ value ≤ 1.0 AND
    min_x ≤ max_x AND min_y ≤ max_y
    
    Validates: Requirements 4.8
    """
    # Generate image size
    image_size = data.draw(valid_image_dimensions())
    
    # Generate padding based on image size
    padding = data.draw(valid_padding(image_size))
    
    # Generate box coordinates based on image size and padding
    box = data.draw(valid_box_coordinates(image_size, padding))
    
    # Create screenshot processor
    config = ScreenshotConfig(
        supported_apps=["whatsapp", "telegram"],
        supported_languages=["en", "zh"],
        default_conf_threshold=0.5
    )
    processor = ScreenshotProcessor(config)
    
    # Normalize coordinates
    normalized = processor._normalize_coordinates(box, padding, image_size)
    
    # Verify the property: all coordinates should be in [0.0, 1.0]
    assert len(normalized) == 4, "Normalized coordinates must have 4 values"
    
    min_x, min_y, max_x, max_y = normalized
    
    # Property part 1: All values should be in range [0.0, 1.0]
    assert 0.0 <= min_x <= 1.0, \
        f"min_x must be in [0.0, 1.0], got {min_x}"
    assert 0.0 <= min_y <= 1.0, \
        f"min_y must be in [0.0, 1.0], got {min_y}"
    assert 0.0 <= max_x <= 1.0, \
        f"max_x must be in [0.0, 1.0], got {max_x}"
    assert 0.0 <= max_y <= 1.0, \
        f"max_y must be in [0.0, 1.0], got {max_y}"
    
    # Property part 2: min_x ≤ max_x AND min_y ≤ max_y
    assert min_x <= max_x, \
        f"min_x ({min_x}) must be <= max_x ({max_x})"
    assert min_y <= max_y, \
        f"min_y ({min_y}) must be <= max_y ({max_y})"


# Additional test: Edge cases with extreme coordinates
@given(
    image_width=st.integers(min_value=100, max_value=5000),
    image_height=st.integers(min_value=100, max_value=5000),
)
def test_coordinate_normalization_edge_cases(image_width, image_height):
    """Test coordinate normalization with edge cases like boxes at image boundaries."""
    config = ScreenshotConfig(
        supported_apps=["whatsapp", "telegram"],
        supported_languages=["en", "zh"],
        default_conf_threshold=0.5
    )
    processor = ScreenshotProcessor(config)
    
    image_size = [image_width, image_height]
    padding = [0, 0, 0, 0]  # No padding
    
    # Test case 1: Box at top-left corner
    box_top_left = MockBox(0, 0, 100, 100)
    normalized = processor._normalize_coordinates(box_top_left, padding, image_size)
    min_x, min_y, max_x, max_y = normalized
    
    assert 0.0 <= min_x <= 1.0
    assert 0.0 <= min_y <= 1.0
    assert 0.0 <= max_x <= 1.0
    assert 0.0 <= max_y <= 1.0
    assert min_x <= max_x
    assert min_y <= max_y
    assert min_x == 0.0, "Box at left edge should have min_x = 0.0"
    assert min_y == 0.0, "Box at top edge should have min_y = 0.0"
    
    # Test case 2: Box at bottom-right corner
    box_bottom_right = MockBox(
        image_width - 100, image_height - 100,
        image_width, image_height
    )
    normalized = processor._normalize_coordinates(box_bottom_right, padding, image_size)
    min_x, min_y, max_x, max_y = normalized
    
    assert 0.0 <= min_x <= 1.0
    assert 0.0 <= min_y <= 1.0
    assert 0.0 <= max_x <= 1.0
    assert 0.0 <= max_y <= 1.0
    assert min_x <= max_x
    assert min_y <= max_y
    assert max_x == 1.0, "Box at right edge should have max_x = 1.0"
    assert max_y == 1.0, "Box at bottom edge should have max_y = 1.0"
    
    # Test case 3: Box spanning entire image
    box_full = MockBox(0, 0, image_width, image_height)
    normalized = processor._normalize_coordinates(box_full, padding, image_size)
    min_x, min_y, max_x, max_y = normalized
    
    assert min_x == 0.0
    assert min_y == 0.0
    assert max_x == 1.0
    assert max_y == 1.0


# Test with padding
@given(
    image_width=st.integers(min_value=200, max_value=5000),
    image_height=st.integers(min_value=200, max_value=5000),
    pad_percent=st.floats(min_value=0.0, max_value=0.2)  # Up to 20% padding
)
def test_coordinate_normalization_with_padding(image_width, image_height, pad_percent):
    """Test coordinate normalization with various padding configurations."""
    config = ScreenshotConfig(
        supported_apps=["whatsapp", "telegram"],
        supported_languages=["en", "zh"],
        default_conf_threshold=0.5
    )
    processor = ScreenshotProcessor(config)
    
    image_size = [image_width, image_height]
    
    # Calculate padding as percentage of image dimensions
    pad_horizontal = int(image_width * pad_percent)
    pad_vertical = int(image_height * pad_percent)
    padding = [pad_vertical, pad_horizontal, pad_vertical, pad_horizontal]
    
    # Create a box in the effective area (after padding)
    effective_width = image_width - 2 * pad_horizontal
    effective_height = image_height - 2 * pad_vertical
    
    # Ensure effective dimensions are positive
    assume(effective_width > 10)
    assume(effective_height > 10)
    
    # Box in the middle of effective area
    box_x_min = pad_horizontal + effective_width // 4
    box_y_min = pad_vertical + effective_height // 4
    box_x_max = pad_horizontal + 3 * effective_width // 4
    box_y_max = pad_vertical + 3 * effective_height // 4
    
    box = MockBox(box_x_min, box_y_min, box_x_max, box_y_max)
    
    # Normalize coordinates
    normalized = processor._normalize_coordinates(box, padding, image_size)
    min_x, min_y, max_x, max_y = normalized
    
    # Verify the property holds even with padding
    assert 0.0 <= min_x <= 1.0, f"min_x must be in [0.0, 1.0], got {min_x}"
    assert 0.0 <= min_y <= 1.0, f"min_y must be in [0.0, 1.0], got {min_y}"
    assert 0.0 <= max_x <= 1.0, f"max_x must be in [0.0, 1.0], got {max_x}"
    assert 0.0 <= max_y <= 1.0, f"max_y must be in [0.0, 1.0], got {max_y}"
    assert min_x <= max_x, f"min_x ({min_x}) must be <= max_x ({max_x})"
    assert min_y <= max_y, f"min_y ({min_y}) must be <= max_y ({max_y})"
    
    # With padding, the box should be somewhere in the middle (not at edges)
    # since we placed it in the effective area
    if pad_percent > 0.05:  # Only check if padding is significant
        assert 0.0 < min_x < 1.0, "Box should not be at left edge with padding"
        assert 0.0 < min_y < 1.0, "Box should not be at top edge with padding"
        assert 0.0 < max_x < 1.0, "Box should not be at right edge with padding"
        assert 0.0 < max_y < 1.0, "Box should not be at bottom edge with padding"


# Test with coordinates outside bounds (should be clamped)
@given(
    image_width=st.integers(min_value=100, max_value=5000),
    image_height=st.integers(min_value=100, max_value=5000),
)
def test_coordinate_normalization_clamping(image_width, image_height):
    """Test that coordinates outside image bounds are clamped to [0.0, 1.0]."""
    config = ScreenshotConfig(
        supported_apps=["whatsapp", "telegram"],
        supported_languages=["en", "zh"],
        default_conf_threshold=0.5
    )
    processor = ScreenshotProcessor(config)
    
    image_size = [image_width, image_height]
    padding = [0, 0, 0, 0]
    
    # Test case 1: Box with negative coordinates (should be clamped to 0.0)
    box_negative = MockBox(-100, -100, 100, 100)
    normalized = processor._normalize_coordinates(box_negative, padding, image_size)
    min_x, min_y, max_x, max_y = normalized
    
    assert min_x >= 0.0, "Negative coordinates should be clamped to 0.0"
    assert min_y >= 0.0, "Negative coordinates should be clamped to 0.0"
    assert 0.0 <= max_x <= 1.0
    assert 0.0 <= max_y <= 1.0
    assert min_x <= max_x
    assert min_y <= max_y
    
    # Test case 2: Box extending beyond image bounds (should be clamped to 1.0)
    box_beyond = MockBox(
        image_width - 100, image_height - 100,
        image_width + 100, image_height + 100
    )
    normalized = processor._normalize_coordinates(box_beyond, padding, image_size)
    min_x, min_y, max_x, max_y = normalized
    
    assert 0.0 <= min_x <= 1.0
    assert 0.0 <= min_y <= 1.0
    assert max_x <= 1.0, "Coordinates beyond image should be clamped to 1.0"
    assert max_y <= 1.0, "Coordinates beyond image should be clamped to 1.0"
    assert min_x <= max_x
    assert min_y <= max_y
