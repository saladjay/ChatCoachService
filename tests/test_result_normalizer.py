"""Unit tests for ResultNormalizer component."""

import pytest
from app.services.result_normalizer import ResultNormalizer
from app.models.screenshot import ImageMeta, ParseOptions


def test_normalize_complete_data():
    """Test normalization with complete valid data."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bubble_id": "b1",
                "bbox": {"x1": 10, "y1": 100, "x2": 200, "y2": 150},
                "center_x": 105,
                "center_y": 125,
                "text": "Hello",
                "sender": "user",
                "column": "right",
                "confidence": 0.9
            },
            {
                "bubble_id": "b2",
                "bbox": {"x1": 10, "y1": 50, "x2": 200, "y2": 90},
                "center_x": 105,
                "center_y": 70,
                "text": "Hi there",
                "sender": "talker",
                "column": "left",
                "confidence": 0.85
            }
        ],
        "layout": {
            "type": "two_columns",
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    result = normalizer.normalize(raw_json, image_meta, options)
    
    # Verify structure
    assert result.image_meta.width == 400
    assert result.image_meta.height == 800
    assert result.participants.self.id == "user1"
    assert result.participants.other.id == "user2"
    assert len(result.bubbles) == 2
    
    # Verify bubbles are sorted by y1 (b2 should come first with y1=50)
    assert result.bubbles[0].bubble_id == "b2"
    assert result.bubbles[0].bbox.y1 == 50
    assert result.bubbles[1].bubble_id == "b1"
    assert result.bubbles[1].bbox.y1 == 100


def test_normalize_with_missing_optional_fields():
    """Test normalization with missing optional fields (center, sender, column, confidence)."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bbox": {"x1": 10, "y1": 100, "x2": 200, "y2": 150},
                "text": "Hello from left"
            },
            {
                "bbox": {"x1": 250, "y1": 50, "x2": 390, "y2": 90},
                "text": "Hello from right"
            }
        ],
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    result = normalizer.normalize(raw_json, image_meta, options)
    
    # Verify defaults were applied
    assert len(result.bubbles) == 2
    
    # Bubbles are sorted by y1, so the right bubble (y1=50) comes first
    # First bubble (right side, y1=50)
    bubble1 = result.bubbles[0]
    assert bubble1.center_x == 320  # (250 + 390) // 2
    assert bubble1.center_y == 70   # (50 + 90) // 2
    assert bubble1.sender == "user"  # Inferred from position (right side)
    assert bubble1.column == "right"
    assert bubble1.confidence == 0.5  # Default
    assert bubble1.bubble_id == "b1"  # Generated (index 1 in original list)
    
    # Second bubble (left side, y1=100)
    bubble2 = result.bubbles[1]
    assert bubble2.center_x == 105  # (10 + 200) // 2
    assert bubble2.center_y == 125  # (100 + 150) // 2
    assert bubble2.sender == "talker"  # Inferred from position (left side)
    assert bubble2.column == "left"
    assert bubble2.confidence == 0.5  # Default
    assert bubble2.bubble_id == "b0"  # Generated (index 0 in original list)


def test_normalize_with_duplicate_ids():
    """Test that duplicate bubble IDs are made unique."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bubble_id": "b1",
                "bbox": {"x1": 10, "y1": 50, "x2": 200, "y2": 90},
                "text": "First"
            },
            {
                "bubble_id": "b1",  # Duplicate
                "bbox": {"x1": 10, "y1": 100, "x2": 200, "y2": 150},
                "text": "Second"
            },
            {
                "bubble_id": "b1",  # Another duplicate
                "bbox": {"x1": 10, "y1": 160, "x2": 200, "y2": 200},
                "text": "Third"
            }
        ],
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    result = normalizer.normalize(raw_json, image_meta, options)
    
    # Verify IDs are unique
    ids = [b.bubble_id for b in result.bubbles]
    assert len(ids) == len(set(ids))  # All unique
    assert "b1" in ids
    assert "b1_1" in ids
    assert "b1_2" in ids


def test_validate_missing_required_fields():
    """Test validation fails when required fields are missing."""
    normalizer = ResultNormalizer()
    
    # Missing participants
    with pytest.raises(ValueError, match="Missing required fields"):
        normalizer._validate_required_fields({
            "bubbles": [],
            "layout": {"left_role": "talker", "right_role": "user"}
        })
    
    # Missing bubbles
    with pytest.raises(ValueError, match="Missing required fields"):
        normalizer._validate_required_fields({
            "participants": {
                "self": {"id": "u1", "nickname": "A"},
                "other": {"id": "u2", "nickname": "B"}
            },
            "layout": {"left_role": "talker", "right_role": "user"}
        })


def test_validate_invalid_sender():
    """Test validation fails for invalid sender values."""
    normalizer = ResultNormalizer()
    
    with pytest.raises(ValueError, match="sender must be 'user' or 'talker'"):
        normalizer._validate_required_fields({
            "participants": {
                "self": {"id": "u1", "nickname": "A"},
                "other": {"id": "u2", "nickname": "B"}
            },
            "bubbles": [
                {
                    "bbox": {"x1": 10, "y1": 50, "x2": 200, "y2": 90},
                    "text": "Hello",
                    "sender": "invalid"
                }
            ],
            "layout": {"left_role": "talker", "right_role": "user"}
        })


def test_calculate_center():
    """Test center point calculation."""
    normalizer = ResultNormalizer()
    from app.models.screenshot import BoundingBox
    
    bbox = BoundingBox(x1=10, y1=20, x2=100, y2=80)
    center_x, center_y = normalizer._calculate_center(bbox)
    
    assert center_x == 55  # (10 + 100) // 2
    assert center_y == 50  # (20 + 80) // 2


def test_infer_sender_from_position():
    """Test sender inference from position."""
    normalizer = ResultNormalizer()
    
    # Left side should be talker
    assert normalizer._infer_sender_from_position(100, 400) == "talker"
    
    # Right side should be user
    assert normalizer._infer_sender_from_position(300, 400) == "user"
    
    # Exactly at midpoint should be user
    assert normalizer._infer_sender_from_position(200, 400) == "user"


def test_bubble_sorting():
    """Test bubbles are sorted by y1 coordinate."""
    normalizer = ResultNormalizer()
    from app.models.screenshot import ChatBubble, BoundingBox
    
    bubbles = [
        ChatBubble(
            bubble_id="b1",
            bbox=BoundingBox(x1=10, y1=100, x2=200, y2=150),
            center_x=105, center_y=125,
            text="Third", sender="user", column="left", confidence=0.9
        ),
        ChatBubble(
            bubble_id="b2",
            bbox=BoundingBox(x1=10, y1=50, x2=200, y2=90),
            center_x=105, center_y=70,
            text="Second", sender="user", column="left", confidence=0.9
        ),
        ChatBubble(
            bubble_id="b3",
            bbox=BoundingBox(x1=10, y1=10, x2=200, y2=40),
            center_x=105, center_y=25,
            text="First", sender="user", column="left", confidence=0.9
        )
    ]
    
    sorted_bubbles = normalizer._sort_bubbles_by_position(bubbles)
    
    assert sorted_bubbles[0].text == "First"
    assert sorted_bubbles[1].text == "Second"
    assert sorted_bubbles[2].text == "Third"


# Task 6.13: Unit tests for missing field handling
def test_missing_participants_field():
    """Test that missing participants field raises error code 1004."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "bubbles": [
            {
                "bbox": {"x1": 10, "y1": 50, "x2": 200, "y2": 90},
                "text": "Hello"
            }
        ],
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    with pytest.raises(ValueError, match="Missing required fields.*participants"):
        normalizer.normalize(raw_json, image_meta, options)


def test_missing_bubbles_field():
    """Test that missing bubbles field raises error code 1004."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    with pytest.raises(ValueError, match="Missing required fields.*bubbles"):
        normalizer.normalize(raw_json, image_meta, options)


def test_missing_layout_field():
    """Test that missing layout field raises error code 1004."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bbox": {"x1": 10, "y1": 50, "x2": 200, "y2": 90},
                "text": "Hello"
            }
        ]
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    with pytest.raises(ValueError, match="Missing required fields.*layout"):
        normalizer.normalize(raw_json, image_meta, options)


def test_missing_participant_self():
    """Test that missing participants.self raises error code 1004."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bbox": {"x1": 10, "y1": 50, "x2": 200, "y2": 90},
                "text": "Hello"
            }
        ],
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    with pytest.raises(ValueError, match="participants must contain 'self' and 'other'"):
        normalizer.normalize(raw_json, image_meta, options)


def test_missing_participant_id():
    """Test that missing participant id raises error code 1004."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"nickname": "Alice"},  # Missing id
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bbox": {"x1": 10, "y1": 50, "x2": 200, "y2": 90},
                "text": "Hello"
            }
        ],
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    with pytest.raises(ValueError, match="participants.self must contain 'id' and 'nickname'"):
        normalizer.normalize(raw_json, image_meta, options)


def test_missing_bubble_bbox():
    """Test that missing bubble bbox raises error code 1004."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "text": "Hello"  # Missing bbox
            }
        ],
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    with pytest.raises(ValueError, match="bubble\\[0\\] missing required fields.*bbox"):
        normalizer.normalize(raw_json, image_meta, options)


def test_missing_bubble_text():
    """Test that missing bubble text raises error code 1004."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bbox": {"x1": 10, "y1": 50, "x2": 200, "y2": 90}
                # Missing text
            }
        ],
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    with pytest.raises(ValueError, match="bubble\\[0\\] missing required fields.*text"):
        normalizer.normalize(raw_json, image_meta, options)


def test_missing_bbox_coordinates():
    """Test that missing bbox coordinates raise error code 1004."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bbox": {"x1": 10, "y1": 50, "x2": 200},  # Missing y2
                "text": "Hello"
            }
        ],
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    with pytest.raises(ValueError, match="bubble\\[0\\].bbox missing coordinates.*y2"):
        normalizer.normalize(raw_json, image_meta, options)


def test_missing_layout_roles():
    """Test that missing layout roles raise error code 1004."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bbox": {"x1": 10, "y1": 50, "x2": 200, "y2": 90},
                "text": "Hello"
            }
        ],
        "layout": {
            "left_role": "talker"
            # Missing right_role
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    with pytest.raises(ValueError, match="layout must contain 'left_role' and 'right_role'"):
        normalizer.normalize(raw_json, image_meta, options)


def test_normalization_with_partial_bubble_data():
    """Test normalization successfully handles bubbles with only required fields."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bbox": {"x1": 50, "y1": 100, "x2": 150, "y2": 140},
                "text": "Minimal bubble"
                # Missing: bubble_id, center_x, center_y, sender, column, confidence
            }
        ],
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    result = normalizer.normalize(raw_json, image_meta, options)
    
    # Verify normalization applied defaults
    assert len(result.bubbles) == 1
    bubble = result.bubbles[0]
    
    # Check calculated center
    assert bubble.center_x == 100  # (50 + 150) // 2
    assert bubble.center_y == 120  # (100 + 140) // 2
    
    # Check inferred sender (left side = talker)
    assert bubble.sender == "talker"
    
    # Check inferred column
    assert bubble.column == "left"
    
    # Check default confidence
    assert bubble.confidence == 0.5
    
    # Check generated bubble_id
    assert bubble.bubble_id == "b0"
    
    # Check text preserved
    assert bubble.text == "Minimal bubble"


def test_normalization_with_multiple_partial_bubbles():
    """Test normalization with multiple bubbles having partial data."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bbox": {"x1": 50, "y1": 200, "x2": 150, "y2": 240},
                "text": "Left bubble"
            },
            {
                "bbox": {"x1": 250, "y1": 100, "x2": 350, "y2": 140},
                "text": "Right bubble"
            },
            {
                "bbox": {"x1": 60, "y1": 300, "x2": 160, "y2": 340},
                "text": "Another left"
            }
        ],
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    result = normalizer.normalize(raw_json, image_meta, options)
    
    # Verify all bubbles normalized
    assert len(result.bubbles) == 3
    
    # Bubbles should be sorted by y1 (100, 200, 300)
    assert result.bubbles[0].text == "Right bubble"
    assert result.bubbles[0].sender == "user"  # Right side
    assert result.bubbles[0].column == "right"
    
    assert result.bubbles[1].text == "Left bubble"
    assert result.bubbles[1].sender == "talker"  # Left side
    assert result.bubbles[1].column == "left"
    
    assert result.bubbles[2].text == "Another left"
    assert result.bubbles[2].sender == "talker"  # Left side
    assert result.bubbles[2].column == "left"
    
    # All should have default confidence
    assert all(b.confidence == 0.5 for b in result.bubbles)
    
    # All should have generated IDs
    assert result.bubbles[0].bubble_id == "b1"  # Original index 1
    assert result.bubbles[1].bubble_id == "b0"  # Original index 0
    assert result.bubbles[2].bubble_id == "b2"  # Original index 2


def test_invalid_bbox_coordinate_type():
    """Test that non-numeric bbox coordinates raise error code 1004."""
    normalizer = ResultNormalizer()
    
    raw_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "Alice"},
            "other": {"id": "user2", "nickname": "Bob"}
        },
        "bubbles": [
            {
                "bbox": {"x1": "10", "y1": 50, "x2": 200, "y2": 90},  # x1 is string
                "text": "Hello"
            }
        ],
        "layout": {
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    image_meta = ImageMeta(width=400, height=800)
    options = ParseOptions()
    
    with pytest.raises(ValueError, match="bubble\\[0\\].bbox.x1 must be a number"):
        normalizer.normalize(raw_json, image_meta, options)
