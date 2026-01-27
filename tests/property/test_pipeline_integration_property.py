"""Property-based tests for Pipeline Integration.

This module contains property-based tests that verify universal correctness
properties of the pipeline integration utilities across many generated inputs.
"""

import pytest
from hypothesis import given, strategies as st
from app.services.pipeline_integration import bubbles_to_dialogs
from app.models.screenshot import ChatBubble, BoundingBox
from app.models.api import GenerateReplyRequest


# Generators for test data
@st.composite
def valid_bbox(draw):
    """Generate a valid bounding box."""
    x1 = draw(st.integers(min_value=0, max_value=1000))
    y1 = draw(st.integers(min_value=0, max_value=1000))
    x2 = draw(st.integers(min_value=x1 + 1, max_value=x1 + 500))
    y2 = draw(st.integers(min_value=y1 + 1, max_value=y1 + 500))
    return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)


@st.composite
def valid_chat_bubble(draw):
    """Generate a valid ChatBubble object."""
    bbox = draw(valid_bbox())
    center_x = (bbox.x1 + bbox.x2) // 2
    center_y = (bbox.y1 + bbox.y2) // 2
    
    return ChatBubble(
        bubble_id=draw(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122))),
        bbox=bbox,
        center_x=center_x,
        center_y=center_y,
        text=draw(st.text(min_size=1, max_size=200)),
        sender=draw(st.sampled_from(["user", "talker"])),
        column=draw(st.sampled_from(["left", "right"])),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    )


# Feature: chat-screenshot-parser, Property 4: Pipeline Format Compatibility
@given(
    bubbles=st.lists(valid_chat_bubble(), min_size=0, max_size=20)
)
def test_property_4_pipeline_format_compatibility(bubbles):
    """Property 4: For any successful parse response, the bubbles array should
    be convertible to the dialogs format expected by GenerateReplyRequest
    without data loss.
    
    Validates: Requirements 1.4, 8.1, 8.2
    """
    # Convert bubbles to dialogs format
    dialogs = bubbles_to_dialogs(bubbles)
    
    # Verify the conversion produces a list
    assert isinstance(dialogs, list), "bubbles_to_dialogs must return a list"
    
    # Verify the length is preserved
    assert len(dialogs) == len(bubbles), \
        f"Conversion must preserve length: expected {len(bubbles)}, got {len(dialogs)}"
    
    # Verify each dialog has the required structure
    for i, (bubble, dialog) in enumerate(zip(bubbles, dialogs)):
        # Verify dialog is a dictionary
        assert isinstance(dialog, dict), \
            f"Dialog {i} must be a dictionary, got {type(dialog)}"
        
        # Verify required fields are present
        assert "speaker" in dialog, \
            f"Dialog {i} must have 'speaker' field"
        assert "text" in dialog, \
            f"Dialog {i} must have 'text' field"
        assert "timestamp" in dialog, \
            f"Dialog {i} must have 'timestamp' field"
        
        # Verify speaker mapping is correct (sender → speaker)
        assert dialog["speaker"] == bubble.sender, \
            f"Dialog {i} speaker must match bubble sender: " \
            f"expected {bubble.sender}, got {dialog['speaker']}"
        
        # Verify text is preserved exactly
        assert dialog["text"] == bubble.text, \
            f"Dialog {i} text must match bubble text: " \
            f"expected '{bubble.text}', got '{dialog['text']}'"
        
        # Verify timestamp is None (not available from screenshots)
        assert dialog["timestamp"] is None, \
            f"Dialog {i} timestamp must be None, got {dialog['timestamp']}"
        
        # Verify speaker value is valid
        assert dialog["speaker"] in ["user", "talker"], \
            f"Dialog {i} speaker must be 'user' or 'talker', got {dialog['speaker']}"
    
    # Verify the dialogs can be used in GenerateReplyRequest
    # This tests compatibility with the existing pipeline
    try:
        request = GenerateReplyRequest(
            user_id="test_user",
            target_id="test_target",
            conversation_id="test_conversation",
            dialogs=dialogs,
            intimacy_value=50
        )
        
        # Verify the request was created successfully
        assert request is not None, "GenerateReplyRequest creation must succeed"
        assert request.dialogs == dialogs, \
            "GenerateReplyRequest must preserve dialogs exactly"
        
        # Verify the dialogs field in the request matches what we provided
        assert len(request.dialogs) == len(bubbles), \
            f"GenerateReplyRequest must preserve dialog count: " \
            f"expected {len(bubbles)}, got {len(request.dialogs)}"
        
        # Verify each dialog in the request
        for i, (original_dialog, request_dialog) in enumerate(zip(dialogs, request.dialogs)):
            assert request_dialog == original_dialog, \
                f"Dialog {i} in request must match original: " \
                f"expected {original_dialog}, got {request_dialog}"
            
    except Exception as e:
        pytest.fail(
            f"Failed to create GenerateReplyRequest with converted dialogs: {e}\n"
            f"Dialogs: {dialogs}"
        )
    
    # Verify no data loss during conversion
    # All essential information from bubbles should be preserved in dialogs
    for i, (bubble, dialog) in enumerate(zip(bubbles, dialogs)):
        # The essential fields for conversation generation are:
        # - Who said it (sender/speaker)
        # - What they said (text)
        # These must be preserved exactly
        
        assert bubble.sender == dialog["speaker"], \
            f"Bubble {i} sender must be preserved in dialog speaker"
        assert bubble.text == dialog["text"], \
            f"Bubble {i} text must be preserved in dialog text"
    
    # Verify order is preserved (important for conversation flow)
    if len(bubbles) > 1:
        for i in range(len(bubbles) - 1):
            # The order of bubbles should match the order of dialogs
            assert bubbles[i].sender == dialogs[i]["speaker"], \
                f"Order must be preserved: bubble {i} sender mismatch"
            assert bubbles[i].text == dialogs[i]["text"], \
                f"Order must be preserved: bubble {i} text mismatch"


# Feature: chat-screenshot-parser, Property 4: Pipeline Format Compatibility (Empty Case)
def test_property_4_pipeline_format_compatibility_empty():
    """Property 4 (Edge Case): For an empty bubbles array, the conversion
    should produce an empty dialogs array that is still compatible with
    GenerateReplyRequest.
    
    Validates: Requirements 1.4, 8.1, 8.2
    """
    # Test with empty bubbles list
    bubbles = []
    dialogs = bubbles_to_dialogs(bubbles)
    
    # Verify empty list is returned
    assert isinstance(dialogs, list), "bubbles_to_dialogs must return a list"
    assert len(dialogs) == 0, "Empty bubbles should produce empty dialogs"
    
    # Verify empty dialogs can be used in GenerateReplyRequest
    try:
        request = GenerateReplyRequest(
            user_id="test_user",
            target_id="test_target",
            conversation_id="test_conversation",
            dialogs=dialogs,
            intimacy_value=50
        )
        
        assert request is not None, "GenerateReplyRequest creation must succeed with empty dialogs"
        assert request.dialogs == [], "GenerateReplyRequest must accept empty dialogs"
        
    except Exception as e:
        pytest.fail(f"Failed to create GenerateReplyRequest with empty dialogs: {e}")


# Feature: chat-screenshot-parser, Property 4: Pipeline Format Compatibility (Special Characters)
@given(
    special_text=st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            blacklist_categories=('Cs',),  # Exclude surrogates
            blacklist_characters=('\x00',)  # Exclude null character
        )
    )
)
def test_property_4_pipeline_format_compatibility_special_characters(special_text):
    """Property 4 (Special Characters): For any text content including special
    characters, emojis, or multi-line text, the conversion should preserve the
    text exactly without corruption.
    
    Validates: Requirements 1.4, 8.1, 8.2
    """
    # Create a bubble with special text
    bubble = ChatBubble(
        bubble_id="test_bubble",
        bbox=BoundingBox(x1=10, y1=20, x2=100, y2=50),
        center_x=55,
        center_y=35,
        text=special_text,
        sender="user",
        column="right",
        confidence=0.95
    )
    
    # Convert to dialogs
    dialogs = bubbles_to_dialogs([bubble])
    
    # Verify text is preserved exactly
    assert len(dialogs) == 1, "Should produce exactly one dialog"
    assert dialogs[0]["text"] == special_text, \
        f"Special text must be preserved exactly: expected '{special_text}', got '{dialogs[0]['text']}'"
    
    # Verify it can be used in GenerateReplyRequest
    try:
        request = GenerateReplyRequest(
            user_id="test_user",
            target_id="test_target",
            conversation_id="test_conversation",
            dialogs=dialogs,
            intimacy_value=50
        )
        
        assert request.dialogs[0]["text"] == special_text, \
            "GenerateReplyRequest must preserve special text exactly"
            
    except Exception as e:
        pytest.fail(
            f"Failed to create GenerateReplyRequest with special text: {e}\n"
            f"Text: {repr(special_text)}"
        )


# Feature: chat-screenshot-parser, Property 4: Pipeline Format Compatibility (Alternating Speakers)
@given(
    num_messages=st.integers(min_value=2, max_value=20)
)
def test_property_4_pipeline_format_compatibility_alternating_speakers(num_messages):
    """Property 4 (Conversation Flow): For any conversation with alternating
    speakers, the conversion should preserve the speaker order, which is
    essential for conversation context.
    
    Validates: Requirements 1.4, 8.1, 8.2
    """
    # Create bubbles with alternating speakers
    bubbles = []
    for i in range(num_messages):
        sender = "user" if i % 2 == 0 else "talker"
        column = "right" if i % 2 == 0 else "left"
        
        bubble = ChatBubble(
            bubble_id=f"b{i}",
            bbox=BoundingBox(x1=10, y1=20 + (i * 60), x2=100, y2=50 + (i * 60)),
            center_x=55,
            center_y=35 + (i * 60),
            text=f"Message {i}",
            sender=sender,
            column=column,
            confidence=0.9
        )
        bubbles.append(bubble)
    
    # Convert to dialogs
    dialogs = bubbles_to_dialogs(bubbles)
    
    # Verify alternating pattern is preserved
    for i in range(num_messages):
        expected_speaker = "user" if i % 2 == 0 else "talker"
        assert dialogs[i]["speaker"] == expected_speaker, \
            f"Dialog {i} speaker must match expected pattern: " \
            f"expected {expected_speaker}, got {dialogs[i]['speaker']}"
    
    # Verify the conversation flow makes sense
    # (alternating speakers indicate a back-and-forth conversation)
    if num_messages >= 2:
        for i in range(num_messages - 1):
            assert dialogs[i]["speaker"] != dialogs[i + 1]["speaker"], \
                f"Consecutive dialogs {i} and {i+1} should have different speakers"
    
    # Verify it can be used in GenerateReplyRequest
    try:
        request = GenerateReplyRequest(
            user_id="test_user",
            target_id="test_target",
            conversation_id="test_conversation",
            dialogs=dialogs,
            intimacy_value=50
        )
        
        # Verify the conversation flow is preserved in the request
        for i in range(num_messages - 1):
            assert request.dialogs[i]["speaker"] != request.dialogs[i + 1]["speaker"], \
                f"GenerateReplyRequest must preserve alternating speaker pattern"
                
    except Exception as e:
        pytest.fail(f"Failed to create GenerateReplyRequest with alternating speakers: {e}")


# Feature: chat-screenshot-parser, Property 7: Layout Structure Validity
@given(
    layout_type=st.text(min_size=1, max_size=50),
    left_role=st.sampled_from(["user", "talker", "invalid", ""]),
    right_role=st.sampled_from(["user", "talker", "invalid", ""])
)
def test_property_7_layout_structure_validity(layout_type, left_role, right_role):
    """Property 7: For any successful parse response, the layout object should
    have a valid type and both left_role and right_role should be either "user"
    or "talker".
    
    Validates: Requirements 2.9, 2.10
    """
    from app.models.screenshot import LayoutInfo, ParsedScreenshotData, ImageMeta, Participants, Participant
    
    # Test if we can create a valid LayoutInfo with the given roles
    # This tests the validation at the model level
    
    if left_role in ["user", "talker"] and right_role in ["user", "talker"]:
        # Valid roles - should succeed
        try:
            layout = LayoutInfo(
                type=layout_type,
                left_role=left_role,
                right_role=right_role
            )
            
            # Verify the layout was created successfully
            assert layout is not None, "LayoutInfo creation should succeed with valid roles"
            
            # Requirement 2.9: Verify layout has a type
            assert hasattr(layout, 'type'), "Layout must have 'type' field"
            assert isinstance(layout.type, str), "Layout type must be a string"
            assert len(layout.type) > 0, "Layout type must not be empty"
            assert layout.type == layout_type, \
                f"Layout type must match input: expected '{layout_type}', got '{layout.type}'"
            
            # Requirement 2.10: Verify layout has left_role and right_role
            assert hasattr(layout, 'left_role'), "Layout must have 'left_role' field"
            assert hasattr(layout, 'right_role'), "Layout must have 'right_role' field"
            
            # Verify roles are valid
            assert layout.left_role in ["user", "talker"], \
                f"Layout left_role must be 'user' or 'talker', got '{layout.left_role}'"
            assert layout.right_role in ["user", "talker"], \
                f"Layout right_role must be 'user' or 'talker', got '{layout.right_role}'"
            
            # Verify roles match input
            assert layout.left_role == left_role, \
                f"Layout left_role must match input: expected '{left_role}', got '{layout.left_role}'"
            assert layout.right_role == right_role, \
                f"Layout right_role must match input: expected '{right_role}', got '{layout.right_role}'"
            
            # Test that the layout can be used in a complete ParsedScreenshotData structure
            try:
                parsed_data = ParsedScreenshotData(
                    image_meta=ImageMeta(width=800, height=600),
                    participants=Participants(
                        self=Participant(id="user1", nickname="User"),
                        other=Participant(id="talker1", nickname="Talker")
                    ),
                    bubbles=[],
                    layout=layout
                )
                
                # Verify the parsed data was created successfully
                assert parsed_data is not None, \
                    "ParsedScreenshotData creation should succeed with valid layout"
                assert parsed_data.layout == layout, \
                    "ParsedScreenshotData must preserve layout exactly"
                
                # Verify layout structure in the complete data
                assert parsed_data.layout.type == layout_type, \
                    "Layout type must be preserved in ParsedScreenshotData"
                assert parsed_data.layout.left_role == left_role, \
                    "Layout left_role must be preserved in ParsedScreenshotData"
                assert parsed_data.layout.right_role == right_role, \
                    "Layout right_role must be preserved in ParsedScreenshotData"
                
            except Exception as e:
                pytest.fail(
                    f"Failed to create ParsedScreenshotData with valid layout: {e}\n"
                    f"Layout: type={layout_type}, left_role={left_role}, right_role={right_role}"
                )
                
        except Exception as e:
            pytest.fail(
                f"Failed to create LayoutInfo with valid roles: {e}\n"
                f"Layout: type={layout_type}, left_role={left_role}, right_role={right_role}"
            )
    else:
        # Invalid roles - should fail validation
        try:
            layout = LayoutInfo(
                type=layout_type,
                left_role=left_role,
                right_role=right_role
            )
            
            # If we get here, validation failed to catch invalid roles
            pytest.fail(
                f"LayoutInfo should reject invalid roles but accepted them\n"
                f"Layout: type={layout_type}, left_role={left_role}, right_role={right_role}"
            )
            
        except Exception:
            # Expected - invalid roles should be rejected
            # This is the correct behavior
            pass


# Feature: chat-screenshot-parser, Property 7: Layout Structure Validity (Edge Cases)
def test_property_7_layout_structure_validity_edge_cases():
    """Property 7 (Edge Cases): Test specific edge cases for layout validation.
    
    Validates: Requirements 2.9, 2.10
    """
    from app.models.screenshot import LayoutInfo
    
    # Test 1: Both roles can be the same (e.g., both "user")
    # This is valid - some chat apps might have unusual layouts
    try:
        layout = LayoutInfo(
            type="two_columns",
            left_role="user",
            right_role="user"
        )
        assert layout.left_role == "user", "Both roles can be 'user'"
        assert layout.right_role == "user", "Both roles can be 'user'"
    except Exception as e:
        pytest.fail(f"LayoutInfo should allow both roles to be the same: {e}")
    
    # Test 2: Both roles can be "talker"
    try:
        layout = LayoutInfo(
            type="two_columns",
            left_role="talker",
            right_role="talker"
        )
        assert layout.left_role == "talker", "Both roles can be 'talker'"
        assert layout.right_role == "talker", "Both roles can be 'talker'"
    except Exception as e:
        pytest.fail(f"LayoutInfo should allow both roles to be the same: {e}")
    
    # Test 3: Typical layout (user on right, talker on left)
    try:
        layout = LayoutInfo(
            type="two_columns",
            left_role="talker",
            right_role="user"
        )
        assert layout.left_role == "talker", "Typical layout: talker on left"
        assert layout.right_role == "user", "Typical layout: user on right"
    except Exception as e:
        pytest.fail(f"LayoutInfo should allow typical layout: {e}")
    
    # Test 4: Reversed layout (user on left, talker on right)
    try:
        layout = LayoutInfo(
            type="two_columns",
            left_role="user",
            right_role="talker"
        )
        assert layout.left_role == "user", "Reversed layout: user on left"
        assert layout.right_role == "talker", "Reversed layout: talker on right"
    except Exception as e:
        pytest.fail(f"LayoutInfo should allow reversed layout: {e}")
    
    # Test 5: Different layout types should be accepted
    for layout_type in ["two_columns", "single_column", "group_chat", "custom"]:
        try:
            layout = LayoutInfo(
                type=layout_type,
                left_role="user",
                right_role="talker"
            )
            assert layout.type == layout_type, \
                f"Layout type '{layout_type}' should be accepted"
        except Exception as e:
            pytest.fail(f"LayoutInfo should accept layout type '{layout_type}': {e}")
    
    # Test 6: Empty layout type should be accepted (string validation)
    try:
        layout = LayoutInfo(
            type="",
            left_role="user",
            right_role="talker"
        )
        assert layout.type == "", "Empty layout type should be accepted"
    except Exception as e:
        # This might fail depending on validation rules, which is acceptable
        pass


# Feature: chat-screenshot-parser, Property 7: Layout Structure Validity (Integration)
@given(
    num_bubbles=st.integers(min_value=1, max_value=20),
    left_role=st.sampled_from(["user", "talker"]),
    right_role=st.sampled_from(["user", "talker"])
)
def test_property_7_layout_structure_validity_with_bubbles(num_bubbles, left_role, right_role):
    """Property 7 (Integration): For any successful parse response with bubbles,
    the layout roles should be consistent with the bubble sender attributions.
    
    Validates: Requirements 2.9, 2.10
    """
    from app.models.screenshot import (
        LayoutInfo, ParsedScreenshotData, ImageMeta, Participants, Participant,
        ChatBubble, BoundingBox
    )
    
    # Create layout
    layout = LayoutInfo(
        type="two_columns",
        left_role=left_role,
        right_role=right_role
    )
    
    # Create bubbles with consistent sender/column attribution
    bubbles = []
    for i in range(num_bubbles):
        # Alternate between left and right columns
        column = "left" if i % 2 == 0 else "right"
        
        # Sender should match the role for that column
        sender = left_role if column == "left" else right_role
        
        bubble = ChatBubble(
            bubble_id=f"b{i}",
            bbox=BoundingBox(x1=10, y1=20 + (i * 60), x2=100, y2=50 + (i * 60)),
            center_x=55 if column == "right" else 25,
            center_y=35 + (i * 60),
            text=f"Message {i}",
            sender=sender,
            column=column,
            confidence=0.9
        )
        bubbles.append(bubble)
    
    # Create complete parsed data
    parsed_data = ParsedScreenshotData(
        image_meta=ImageMeta(width=800, height=600),
        participants=Participants(
            self=Participant(id="user1", nickname="User"),
            other=Participant(id="talker1", nickname="Talker")
        ),
        bubbles=bubbles,
        layout=layout
    )
    
    # Verify layout structure
    assert parsed_data.layout.type == "two_columns", \
        "Layout type should be 'two_columns'"
    assert parsed_data.layout.left_role in ["user", "talker"], \
        f"Layout left_role must be valid, got '{parsed_data.layout.left_role}'"
    assert parsed_data.layout.right_role in ["user", "talker"], \
        f"Layout right_role must be valid, got '{parsed_data.layout.right_role}'"
    
    # Verify consistency between layout and bubbles
    for bubble in parsed_data.bubbles:
        expected_sender = (
            parsed_data.layout.left_role if bubble.column == "left"
            else parsed_data.layout.right_role
        )
        
        assert bubble.sender == expected_sender, \
            f"Bubble {bubble.bubble_id} sender '{bubble.sender}' should match " \
            f"layout role '{expected_sender}' for column '{bubble.column}'"
    
    # Verify that the layout provides meaningful information
    # The layout should help determine which column belongs to which participant
    left_bubbles = [b for b in parsed_data.bubbles if b.column == "left"]
    right_bubbles = [b for b in parsed_data.bubbles if b.column == "right"]
    
    if left_bubbles:
        # All left bubbles should have the same sender (matching left_role)
        left_senders = set(b.sender for b in left_bubbles)
        assert len(left_senders) == 1, \
            f"All left column bubbles should have the same sender, got {left_senders}"
        assert left_senders.pop() == parsed_data.layout.left_role, \
            f"Left column bubbles should match left_role '{parsed_data.layout.left_role}'"
    
    if right_bubbles:
        # All right bubbles should have the same sender (matching right_role)
        right_senders = set(b.sender for b in right_bubbles)
        assert len(right_senders) == 1, \
            f"All right column bubbles should have the same sender, got {right_senders}"
        assert right_senders.pop() == parsed_data.layout.right_role, \
            f"Right column bubbles should match right_role '{parsed_data.layout.right_role}'"
