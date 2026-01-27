"""Tests for pipeline integration utilities.

This module tests the conversion and validation functions that integrate
the screenshot parser output with the conversation generation pipeline.
"""

import pytest

from app.models.screenshot import ChatBubble, BoundingBox, LayoutInfo
from app.services.pipeline_integration import bubbles_to_dialogs, validate_layout


class TestBubblesToDialogs:
    """Tests for the bubbles_to_dialogs conversion function."""

    def test_converts_single_bubble(self):
        """Test conversion of a single bubble to dialog format."""
        bubbles = [
            ChatBubble(
                bubble_id="b1",
                bbox=BoundingBox(x1=10, y1=20, x2=100, y2=50),
                center_x=55,
                center_y=35,
                text="Hello!",
                sender="user",
                column="right",
                confidence=0.95
            )
        ]
        
        dialogs = bubbles_to_dialogs(bubbles)
        
        assert len(dialogs) == 1
        assert dialogs[0]["speaker"] == "user"
        assert dialogs[0]["text"] == "Hello!"
        assert dialogs[0]["timestamp"] is None

    def test_converts_multiple_bubbles(self):
        """Test conversion of multiple bubbles preserves order."""
        bubbles = [
            ChatBubble(
                bubble_id="b1",
                bbox=BoundingBox(x1=10, y1=20, x2=100, y2=50),
                center_x=55,
                center_y=35,
                text="Hello!",
                sender="user",
                column="right",
                confidence=0.95
            ),
            ChatBubble(
                bubble_id="b2",
                bbox=BoundingBox(x1=10, y1=60, x2=100, y2=90),
                center_x=55,
                center_y=75,
                text="Hi there!",
                sender="talker",
                column="left",
                confidence=0.92
            ),
            ChatBubble(
                bubble_id="b3",
                bbox=BoundingBox(x1=10, y1=100, x2=100, y2=130),
                center_x=55,
                center_y=115,
                text="How are you?",
                sender="user",
                column="right",
                confidence=0.88
            )
        ]
        
        dialogs = bubbles_to_dialogs(bubbles)
        
        assert len(dialogs) == 3
        assert dialogs[0]["speaker"] == "user"
        assert dialogs[0]["text"] == "Hello!"
        assert dialogs[1]["speaker"] == "talker"
        assert dialogs[1]["text"] == "Hi there!"
        assert dialogs[2]["speaker"] == "user"
        assert dialogs[2]["text"] == "How are you?"
        
        # All timestamps should be None
        for dialog in dialogs:
            assert dialog["timestamp"] is None

    def test_converts_empty_list(self):
        """Test conversion of empty bubble list."""
        bubbles = []
        dialogs = bubbles_to_dialogs(bubbles)
        assert dialogs == []

    def test_preserves_text_content(self):
        """Test that text content is preserved exactly."""
        bubbles = [
            ChatBubble(
                bubble_id="b1",
                bbox=BoundingBox(x1=10, y1=20, x2=100, y2=50),
                center_x=55,
                center_y=35,
                text="Text with special chars: !@#$%^&*()",
                sender="user",
                column="right",
                confidence=0.95
            ),
            ChatBubble(
                bubble_id="b2",
                bbox=BoundingBox(x1=10, y1=60, x2=100, y2=90),
                center_x=55,
                center_y=75,
                text="Multi\nline\ntext",
                sender="talker",
                column="left",
                confidence=0.92
            )
        ]
        
        dialogs = bubbles_to_dialogs(bubbles)
        
        assert dialogs[0]["text"] == "Text with special chars: !@#$%^&*()"
        assert dialogs[1]["text"] == "Multi\nline\ntext"


class TestValidateLayout:
    """Tests for the validate_layout function."""

    def test_valid_layout_with_consistent_bubbles(self):
        """Test validation passes for valid layout and consistent bubbles."""
        layout = LayoutInfo(
            type="two_columns",
            left_role="talker",
            right_role="user"
        )
        bubbles = [
            ChatBubble(
                bubble_id="b1",
                bbox=BoundingBox(x1=10, y1=20, x2=100, y2=50),
                center_x=55,
                center_y=35,
                text="Hello!",
                sender="user",
                column="right",
                confidence=0.95
            ),
            ChatBubble(
                bubble_id="b2",
                bbox=BoundingBox(x1=10, y1=60, x2=100, y2=90),
                center_x=55,
                center_y=75,
                text="Hi there!",
                sender="talker",
                column="left",
                confidence=0.92
            )
        ]
        
        result = validate_layout(layout, bubbles)
        assert result is True

    def test_invalid_layout_type(self):
        """Test validation fails for invalid layout type."""
        layout = LayoutInfo(
            type="single_column",
            left_role="talker",
            right_role="user"
        )
        bubbles = []
        
        with pytest.raises(ValueError) as exc_info:
            validate_layout(layout, bubbles)
        
        assert "Invalid layout type" in str(exc_info.value)
        assert "single_column" in str(exc_info.value)

    def test_same_roles_for_left_and_right(self):
        """Test validation fails when left and right roles are the same."""
        layout = LayoutInfo(
            type="two_columns",
            left_role="user",
            right_role="user"
        )
        bubbles = []
        
        with pytest.raises(ValueError) as exc_info:
            validate_layout(layout, bubbles)
        
        assert "cannot be the same" in str(exc_info.value)

    def test_inconsistent_bubble_attribution(self):
        """Test validation fails when bubble sender doesn't match layout."""
        layout = LayoutInfo(
            type="two_columns",
            left_role="talker",
            right_role="user"
        )
        bubbles = [
            ChatBubble(
                bubble_id="b1",
                bbox=BoundingBox(x1=10, y1=20, x2=100, y2=50),
                center_x=55,
                center_y=35,
                text="Hello!",
                sender="talker",  # Should be "user" for right column
                column="right",
                confidence=0.95
            )
        ]
        
        with pytest.raises(ValueError) as exc_info:
            validate_layout(layout, bubbles)
        
        assert "Inconsistent sender attribution" in str(exc_info.value)
        assert "b1" in str(exc_info.value)

    def test_valid_layout_with_empty_bubbles(self):
        """Test validation passes for valid layout with no bubbles."""
        layout = LayoutInfo(
            type="two_columns",
            left_role="talker",
            right_role="user"
        )
        bubbles = []
        
        result = validate_layout(layout, bubbles)
        assert result is True

    def test_valid_layout_with_multiple_bubbles(self):
        """Test validation passes for multiple consistent bubbles."""
        layout = LayoutInfo(
            type="two_columns",
            left_role="talker",
            right_role="user"
        )
        bubbles = [
            ChatBubble(
                bubble_id="b1",
                bbox=BoundingBox(x1=10, y1=20, x2=100, y2=50),
                center_x=55,
                center_y=35,
                text="Hello!",
                sender="user",
                column="right",
                confidence=0.95
            ),
            ChatBubble(
                bubble_id="b2",
                bbox=BoundingBox(x1=10, y1=60, x2=100, y2=90),
                center_x=55,
                center_y=75,
                text="Hi!",
                sender="talker",
                column="left",
                confidence=0.92
            ),
            ChatBubble(
                bubble_id="b3",
                bbox=BoundingBox(x1=10, y1=100, x2=100, y2=130),
                center_x=55,
                center_y=115,
                text="How are you?",
                sender="user",
                column="right",
                confidence=0.88
            ),
            ChatBubble(
                bubble_id="b4",
                bbox=BoundingBox(x1=10, y1=140, x2=100, y2=170),
                center_x=55,
                center_y=155,
                text="Good!",
                sender="talker",
                column="left",
                confidence=0.90
            )
        ]
        
        result = validate_layout(layout, bubbles)
        assert result is True
