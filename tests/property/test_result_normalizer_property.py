"""Property-based tests for Result Normalizer component.

This module contains property-based tests that verify universal correctness
properties of the ResultNormalizer component across many generated inputs.
"""

import pytest
from hypothesis import given, strategies as st, assume
from app.services.result_normalizer import ResultNormalizer
from app.models.screenshot import ImageMeta, ParseOptions, BoundingBox


# Generators for test data
@st.composite
def valid_bbox(draw):
    """Generate a valid bounding box."""
    x1 = draw(st.integers(min_value=0, max_value=1000))
    y1 = draw(st.integers(min_value=0, max_value=1000))
    x2 = draw(st.integers(min_value=x1 + 1, max_value=x1 + 500))
    y2 = draw(st.integers(min_value=y1 + 1, max_value=y1 + 500))
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


@st.composite
def valid_bubble(draw, include_optional=True):
    """Generate a valid bubble dictionary."""
    bbox = draw(valid_bbox())
    bubble = {
        "bbox": bbox,
        "text": draw(st.text(min_size=1, max_size=100)),
    }
    
    if include_optional:
        # Randomly include optional fields
        if draw(st.booleans()):
            bubble["bubble_id"] = draw(st.text(min_size=1, max_size=20))
        if draw(st.booleans()):
            bubble["center_x"] = draw(st.integers(min_value=0, max_value=1500))
        if draw(st.booleans()):
            bubble["center_y"] = draw(st.integers(min_value=0, max_value=1500))
        if draw(st.booleans()):
            bubble["sender"] = draw(st.sampled_from(["user", "talker"]))
        if draw(st.booleans()):
            bubble["column"] = draw(st.sampled_from(["left", "right"]))
        if draw(st.booleans()):
            bubble["confidence"] = draw(st.floats(min_value=0.0, max_value=1.0))
    
    return bubble


@st.composite
def valid_raw_json(draw, num_bubbles=None):
    """Generate a valid raw JSON response."""
    if num_bubbles is None:
        num_bubbles = draw(st.integers(min_value=1, max_value=10))
    else:
        # If num_bubbles is a strategy, draw from it
        if hasattr(num_bubbles, 'example'):
            num_bubbles = draw(num_bubbles)
    
    bubbles = [draw(valid_bubble()) for _ in range(num_bubbles)]
    
    return {
        "participants": {
            "self": {
                "id": draw(st.text(min_size=1, max_size=20)),
                "nickname": draw(st.text(min_size=1, max_size=30))
            },
            "other": {
                "id": draw(st.text(min_size=1, max_size=20)),
                "nickname": draw(st.text(min_size=1, max_size=30))
            }
        },
        "bubbles": bubbles,
        "layout": {
            "type": "two_columns",
            "left_role": draw(st.sampled_from(["user", "talker"])),
            "right_role": draw(st.sampled_from(["user", "talker"]))
        }
    }


# Feature: chat-screenshot-parser, Property 5: Bubble Completeness and Validity
@given(
    raw_json=valid_raw_json(),
    image_width=st.integers(min_value=100, max_value=2000),
    image_height=st.integers(min_value=100, max_value=2000)
)
def test_property_5_bubble_completeness_and_validity(raw_json, image_width, image_height):
    """Property 5: For any bubble in the output bubbles array, it should contain
    all required fields with valid values.
    
    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 4.2, 4.3, 4.4, 9.8, 9.9
    """
    normalizer = ResultNormalizer()
    image_meta = ImageMeta(width=image_width, height=image_height)
    options = ParseOptions()
    
    result = normalizer.normalize(raw_json, image_meta, options)
    
    # Verify all bubbles have required fields
    for bubble in result.bubbles:
        # Check all required fields exist
        assert hasattr(bubble, 'bubble_id')
        assert hasattr(bubble, 'bbox')
        assert hasattr(bubble, 'center_x')
        assert hasattr(bubble, 'center_y')
        assert hasattr(bubble, 'text')
        assert hasattr(bubble, 'sender')
        assert hasattr(bubble, 'column')
        assert hasattr(bubble, 'confidence')
        
        # Check bbox has all coordinates
        assert hasattr(bubble.bbox, 'x1')
        assert hasattr(bubble.bbox, 'y1')
        assert hasattr(bubble.bbox, 'x2')
        assert hasattr(bubble.bbox, 'y2')
        
        # Validate field values
        assert bubble.sender in ["user", "talker"], f"Invalid sender: {bubble.sender}"
        assert bubble.column in ["left", "right"], f"Invalid column: {bubble.column}"
        assert 0.0 <= bubble.confidence <= 1.0, f"Invalid confidence: {bubble.confidence}"
        
        # Validate bbox coordinates are numbers
        assert isinstance(bubble.bbox.x1, (int, float))
        assert isinstance(bubble.bbox.y1, (int, float))
        assert isinstance(bubble.bbox.x2, (int, float))
        assert isinstance(bubble.bbox.y2, (int, float))


# Feature: chat-screenshot-parser, Property 6: Bubble ID Uniqueness
@given(
    raw_json=valid_raw_json(num_bubbles=st.integers(min_value=2, max_value=20)),
    image_width=st.integers(min_value=100, max_value=2000),
    image_height=st.integers(min_value=100, max_value=2000)
)
def test_property_6_bubble_id_uniqueness(raw_json, image_width, image_height):
    """Property 6: For any set of bubbles in a parse response, all bubble_id
    values should be unique within that response.
    
    Validates: Requirements 2.6, 4.9
    """
    # Introduce duplicate IDs to test uniqueness enforcement
    if len(raw_json["bubbles"]) >= 2:
        # Make some bubbles have the same ID
        duplicate_id = "duplicate_test_id"
        raw_json["bubbles"][0]["bubble_id"] = duplicate_id
        raw_json["bubbles"][1]["bubble_id"] = duplicate_id
    
    normalizer = ResultNormalizer()
    image_meta = ImageMeta(width=image_width, height=image_height)
    options = ParseOptions()
    
    result = normalizer.normalize(raw_json, image_meta, options)
    
    # Collect all bubble IDs
    bubble_ids = [bubble.bubble_id for bubble in result.bubbles]
    
    # Verify all IDs are unique
    assert len(bubble_ids) == len(set(bubble_ids)), \
        f"Duplicate bubble IDs found: {bubble_ids}"


# Feature: chat-screenshot-parser, Property 10: Center Point Calculation
@given(
    bbox_dict=valid_bbox(),
    image_width=st.integers(min_value=100, max_value=2000),
    image_height=st.integers(min_value=100, max_value=2000)
)
def test_property_10_center_point_calculation(bbox_dict, image_width, image_height):
    """Property 10: For any bubble with a bounding box, if center_x or center_y
    are not provided by the LLM, the Result_Normalizer should calculate them.
    
    Validates: Requirements 4.5
    """
    normalizer = ResultNormalizer()
    
    # Create a bubble without center coordinates
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "User"},
            "other": {"id": "talker1", "nickname": "Talker"}
        },
        "bubbles": [{
            "bbox": bbox_dict,
            "text": "Test message"
            # No center_x or center_y provided
        }],
        "layout": {
            "type": "two_columns",
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=image_width, height=image_height)
    options = ParseOptions()
    
    result = normalizer.normalize(raw_json, image_meta, options)
    
    # Verify center was calculated
    bubble = result.bubbles[0]
    expected_center_x = (bbox_dict["x1"] + bbox_dict["x2"]) // 2
    expected_center_y = (bbox_dict["y1"] + bbox_dict["y2"]) // 2
    
    assert bubble.center_x == expected_center_x, \
        f"center_x should be {expected_center_x}, got {bubble.center_x}"
    assert bubble.center_y == expected_center_y, \
        f"center_y should be {expected_center_y}, got {bubble.center_y}"


# Feature: chat-screenshot-parser, Property 11: Bubble Sorting by Vertical Position
@given(
    y1_positions=st.lists(st.integers(min_value=0, max_value=1000), min_size=2, max_size=20),
    image_width=st.integers(min_value=100, max_value=2000),
    image_height=st.integers(min_value=100, max_value=2000)
)
def test_property_11_bubble_sorting_by_vertical_position(y1_positions, image_width, image_height):
    """Property 11: For any set of bubbles, the output bubbles array should be
    sorted in ascending order by y1 coordinate (top to bottom).
    
    Validates: Requirements 4.6
    """
    normalizer = ResultNormalizer()
    
    # Create bubbles with the given y1 positions
    bubbles = []
    for i, y1 in enumerate(y1_positions):
        bubbles.append({
            "bbox": {
                "x1": 100,
                "y1": y1,
                "x2": 200,
                "y2": y1 + 50
            },
            "text": f"Message {i}"
        })
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "User"},
            "other": {"id": "talker1", "nickname": "Talker"}
        },
        "bubbles": bubbles,
        "layout": {
            "type": "two_columns",
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=image_width, height=image_height)
    options = ParseOptions()
    
    result = normalizer.normalize(raw_json, image_meta, options)
    
    # Verify bubbles are sorted by y1
    y1_values = [bubble.bbox.y1 for bubble in result.bubbles]
    assert y1_values == sorted(y1_values), \
        f"Bubbles not sorted by y1: {y1_values}"


# Feature: chat-screenshot-parser, Property 12: Default Confidence Assignment
@given(
    image_width=st.integers(min_value=100, max_value=2000),
    image_height=st.integers(min_value=100, max_value=2000)
)
def test_property_12_default_confidence_assignment(image_width, image_height):
    """Property 12: For any bubble missing a confidence score, the
    Result_Normalizer should assign a default value of 0.5.
    
    Validates: Requirements 4.7
    """
    normalizer = ResultNormalizer()
    
    # Create a bubble without confidence
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "User"},
            "other": {"id": "talker1", "nickname": "Talker"}
        },
        "bubbles": [{
            "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 150},
            "text": "Test message"
            # No confidence provided
        }],
        "layout": {
            "type": "two_columns",
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=image_width, height=image_height)
    options = ParseOptions()
    
    result = normalizer.normalize(raw_json, image_meta, options)
    
    # Verify default confidence was assigned
    bubble = result.bubbles[0]
    assert bubble.confidence == 0.5, \
        f"Default confidence should be 0.5, got {bubble.confidence}"


# Feature: chat-screenshot-parser, Property 13: Fallback Logic for Invalid Attribution
@given(
    center_x=st.integers(min_value=0, max_value=2000),
    image_width=st.integers(min_value=100, max_value=2000),
    image_height=st.integers(min_value=100, max_value=2000)
)
def test_property_13_fallback_logic_for_invalid_attribution(center_x, image_width, image_height):
    """Property 13: For any bubble with missing or invalid sender/column values,
    the Result_Normalizer should infer them based on center_x position.
    
    Validates: Requirements 4.8, 7.7, 7.8
    """
    # Ensure center_x is within image bounds
    assume(center_x < image_width)
    
    normalizer = ResultNormalizer()
    
    # Create a bubble without sender/column
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "User"},
            "other": {"id": "talker1", "nickname": "Talker"}
        },
        "bubbles": [{
            "bbox": {"x1": center_x - 50, "y1": 100, "x2": center_x + 50, "y2": 150},
            "text": "Test message",
            "center_x": center_x,
            "center_y": 125
            # No sender or column provided
        }],
        "layout": {
            "type": "two_columns",
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=image_width, height=image_height)
    options = ParseOptions()
    
    result = normalizer.normalize(raw_json, image_meta, options)
    
    # Verify fallback logic was applied
    bubble = result.bubbles[0]
    
    if center_x < image_width / 2:
        # Left side
        assert bubble.sender == "talker", \
            f"Left side should be talker, got {bubble.sender}"
        assert bubble.column == "left", \
            f"Left side should be left column, got {bubble.column}"
    else:
        # Right side
        assert bubble.sender == "user", \
            f"Right side should be user, got {bubble.sender}"
        assert bubble.column == "right", \
            f"Right side should be right column, got {bubble.column}"
