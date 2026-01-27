"""Pipeline integration utilities for chat screenshot parser.

This module provides utility functions for integrating the screenshot parser
output with the existing conversation generation pipeline.
"""

from typing import Any

from app.models.screenshot import ChatBubble, LayoutInfo


def bubbles_to_dialogs(bubbles: list[ChatBubble]) -> list[dict[str, Any]]:
    """Convert ChatBubble list to dialogs format for GenerateReplyRequest.
    
    This function transforms the structured bubble data from screenshot parsing
    into the dialogs format expected by the conversation generation pipeline.
    
    The conversion maps:
    - bubble.sender → dialog.speaker
    - bubble.text → dialog.text
    - timestamp is set to None (not available from screenshots)
    
    Args:
        bubbles: List of ChatBubble objects from screenshot parsing
        
    Returns:
        List of dialog dictionaries compatible with GenerateReplyRequest.dialogs
        
    Example:
        >>> bubbles = [
        ...     ChatBubble(
        ...         bubble_id="b1",
        ...         bbox=BoundingBox(x1=10, y1=20, x2=100, y2=50),
        ...         center_x=55,
        ...         center_y=35,
        ...         text="Hello!",
        ...         sender="user",
        ...         column="right",
        ...         confidence=0.95
        ...     ),
        ...     ChatBubble(
        ...         bubble_id="b2",
        ...         bbox=BoundingBox(x1=10, y1=60, x2=100, y2=90),
        ...         center_x=55,
        ...         center_y=75,
        ...         text="Hi there!",
        ...         sender="talker",
        ...         column="left",
        ...         confidence=0.92
        ...     )
        ... ]
        >>> dialogs = bubbles_to_dialogs(bubbles)
        >>> dialogs[0]
        {'speaker': 'user', 'text': 'Hello!', 'timestamp': None}
        >>> dialogs[1]
        {'speaker': 'talker', 'text': 'Hi there!', 'timestamp': None}
    """
    return [
        {
            "speaker": bubble.sender,
            "text": bubble.text,
            "timestamp": None,  # Not available from screenshot
        }
        for bubble in bubbles
    ]


def validate_layout(layout: LayoutInfo, bubbles: list[ChatBubble]) -> bool:
    """Validate layout type and role mappings for consistency.
    
    This function ensures that:
    1. Layout type is valid (currently only "two_columns" is supported)
    2. left_role and right_role are valid values ("user" or "talker")
    3. left_role and right_role are different (no ambiguity)
    4. Bubble sender attributions are consistent with layout role mappings
    
    Args:
        layout: LayoutInfo object describing the chat UI layout
        bubbles: List of ChatBubble objects to validate against layout
        
    Returns:
        True if layout is valid and consistent with bubbles, False otherwise
        
    Raises:
        ValueError: If layout validation fails with a descriptive error message
        
    Example:
        >>> layout = LayoutInfo(
        ...     type="two_columns",
        ...     left_role="talker",
        ...     right_role="user"
        ... )
        >>> bubbles = [
        ...     ChatBubble(..., sender="user", column="right", ...),
        ...     ChatBubble(..., sender="talker", column="left", ...)
        ... ]
        >>> validate_layout(layout, bubbles)
        True
    """
    # Validate layout type
    if layout.type != "two_columns":
        raise ValueError(
            f"Invalid layout type: {layout.type}. "
            f"Only 'two_columns' is currently supported."
        )
    
    # Note: left_role and right_role are validated by Pydantic Literal types
    # so we don't need to check if they're "user" or "talker"
    
    # Validate that roles are different (no ambiguity)
    if layout.left_role == layout.right_role:
        raise ValueError(
            f"left_role and right_role cannot be the same: {layout.left_role}. "
            f"Layout must distinguish between user and talker."
        )
    
    # Validate consistency between layout and bubble attributions
    for bubble in bubbles:
        expected_sender = (
            layout.left_role if bubble.column == "left" else layout.right_role
        )
        if bubble.sender != expected_sender:
            raise ValueError(
                f"Inconsistent sender attribution for bubble {bubble.bubble_id}: "
                f"sender={bubble.sender}, column={bubble.column}, "
                f"but layout maps {bubble.column} to {expected_sender}. "
                f"Layout: left={layout.left_role}, right={layout.right_role}."
            )
    
    return True
