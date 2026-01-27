"""Example demonstrating end-to-end integration of screenshot parsing with reply generation.

This example shows how to:
1. Parse a chat screenshot to extract structured conversation data
2. Convert the parsed bubbles to dialogs format
3. Validate the layout consistency
4. Use the dialogs to generate a reply

Note: This is a demonstration of the integration flow. In production, you would
use actual image URLs and have the services properly configured.
"""

import asyncio
from app.models.screenshot import (
    ParseScreenshotRequest,
    ParseOptions,
    ChatBubble,
    BoundingBox,
    LayoutInfo,
)
from app.models.api import GenerateReplyRequest
from app.services.pipeline_integration import bubbles_to_dialogs, validate_layout


async def demonstrate_integration():
    """Demonstrate the integration between screenshot parsing and reply generation."""
    
    print("=" * 80)
    print("Screenshot Parser to Reply Generation Integration Example")
    print("=" * 80)
    print()
    
    # Step 1: Create a parse request (in production, this would come from an API call)
    print("Step 1: Create parse request")
    parse_request = ParseScreenshotRequest(
        image_url="https://example.com/chat_screenshot.png",
        session_id="demo-session-123",
        options=ParseOptions(
            need_nickname=True,
            need_sender=True,
            force_two_columns=True,
            app_type="wechat"
        )
    )
    print(f"  Image URL: {parse_request.image_url}")
    print(f"  Session ID: {parse_request.session_id}")
    print(f"  App Type: {parse_request.options.app_type}")
    print()
    
    # Step 2: Simulate parsed screenshot data (in production, this comes from the parser service)
    print("Step 2: Simulate parsed screenshot data")
    bubbles = [
        ChatBubble(
            bubble_id="b1",
            bbox=BoundingBox(x1=50, y1=100, x2=300, y2=150),
            center_x=175,
            center_y=125,
            text="Hey! How are you doing?",
            sender="user",
            column="right",
            confidence=0.95
        ),
        ChatBubble(
            bubble_id="b2",
            bbox=BoundingBox(x1=50, y1=170, x2=300, y2=220),
            center_x=175,
            center_y=195,
            text="I'm doing great! Thanks for asking 😊",
            sender="talker",
            column="left",
            confidence=0.92
        ),
        ChatBubble(
            bubble_id="b3",
            bbox=BoundingBox(x1=50, y1=240, x2=300, y2=290),
            center_x=175,
            center_y=265,
            text="Want to grab coffee later?",
            sender="user",
            column="right",
            confidence=0.88
        ),
    ]
    
    layout = LayoutInfo(
        type="two_columns",
        left_role="talker",
        right_role="user"
    )
    
    print(f"  Extracted {len(bubbles)} chat bubbles")
    for bubble in bubbles:
        print(f"    - [{bubble.sender}] {bubble.text[:40]}...")
    print()
    
    # Step 3: Validate layout consistency
    print("Step 3: Validate layout consistency")
    try:
        is_valid = validate_layout(layout, bubbles)
        print(f"  ✓ Layout validation passed: {is_valid}")
        print(f"    Layout: {layout.type}")
        print(f"    Left column: {layout.left_role}")
        print(f"    Right column: {layout.right_role}")
    except ValueError as e:
        print(f"  ✗ Layout validation failed: {e}")
        return
    print()
    
    # Step 4: Convert bubbles to dialogs format
    print("Step 4: Convert bubbles to dialogs format")
    dialogs = bubbles_to_dialogs(bubbles)
    print(f"  Converted {len(dialogs)} bubbles to dialogs")
    for i, dialog in enumerate(dialogs, 1):
        print(f"    Dialog {i}:")
        print(f"      Speaker: {dialog['speaker']}")
        print(f"      Text: {dialog['text']}")
        print(f"      Timestamp: {dialog['timestamp']}")
    print()
    
    # Step 5: Create GenerateReplyRequest
    print("Step 5: Create GenerateReplyRequest")
    gen_request = GenerateReplyRequest(
        user_id="user_123",
        target_id="talker_456",
        conversation_id="conv_789",
        dialogs=dialogs,
        intimacy_value=50,  # Default or from user profile
        language="en",
        quality="normal"
    )
    print(f"  User ID: {gen_request.user_id}")
    print(f"  Target ID: {gen_request.target_id}")
    print(f"  Conversation ID: {gen_request.conversation_id}")
    print(f"  Dialogs: {len(gen_request.dialogs)} messages")
    print(f"  Intimacy Value: {gen_request.intimacy_value}")
    print()
    
    # Step 6: Summary
    print("Step 6: Integration Summary")
    print("  ✓ Screenshot parsed successfully")
    print("  ✓ Layout validated")
    print("  ✓ Bubbles converted to dialogs")
    print("  ✓ GenerateReplyRequest created")
    print()
    print("Next step: Pass gen_request to orchestrator.generate_reply()")
    print("  reply = await orchestrator.generate_reply(gen_request)")
    print()
    print("=" * 80)


def demonstrate_validation_failure():
    """Demonstrate what happens when layout validation fails."""
    
    print()
    print("=" * 80)
    print("Layout Validation Failure Example")
    print("=" * 80)
    print()
    
    # Create inconsistent data
    print("Creating inconsistent layout and bubbles...")
    layout = LayoutInfo(
        type="two_columns",
        left_role="talker",
        right_role="user"
    )
    
    # This bubble has inconsistent attribution
    bubbles = [
        ChatBubble(
            bubble_id="b1",
            bbox=BoundingBox(x1=50, y1=100, x2=300, y2=150),
            center_x=175,
            center_y=125,
            text="Hello!",
            sender="talker",  # Should be "user" for right column
            column="right",
            confidence=0.95
        )
    ]
    
    print(f"  Layout: left={layout.left_role}, right={layout.right_role}")
    print(f"  Bubble: sender={bubbles[0].sender}, column={bubbles[0].column}")
    print()
    
    print("Attempting validation...")
    try:
        validate_layout(layout, bubbles)
        print("  ✓ Validation passed (unexpected!)")
    except ValueError as e:
        print(f"  ✗ Validation failed (expected):")
        print(f"    {e}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    # Run the successful integration example
    asyncio.run(demonstrate_integration())
    
    # Run the validation failure example
    demonstrate_validation_failure()
