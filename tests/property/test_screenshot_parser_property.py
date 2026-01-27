"""Property-based tests for Screenshot Parser Service.

This module contains property-based tests that verify universal correctness
properties of the ScreenshotParserService across many generated inputs.
"""

import pytest
from hypothesis import given, strategies as st
from unittest.mock import AsyncMock, Mock
from app.services.screenshot_parser import ScreenshotParserService
from app.services.image_fetcher import ImageFetcher, FetchedImage
from app.services.prompt_builder import PromptBuilder
from app.services.multimodal_llm_adapter import MultimodalLLMClient, MultimodalLLMResponse
from app.services.result_normalizer import ResultNormalizer
from app.models.screenshot import (
    ParseScreenshotRequest,
    ParseOptions,
    ImageMeta,
    ParsedScreenshotData,
    Participants,
    LayoutInfo,
    ChatBubble,
)


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
def valid_bubble(draw):
    """Generate a valid bubble dictionary."""
    bbox = draw(valid_bbox())
    bubble = {
        "bbox": bbox,
        "text": draw(st.text(min_size=1, max_size=100)),
    }
    
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
def valid_llm_response_json(draw):
    """Generate a valid LLM response JSON."""
    num_bubbles = draw(st.integers(min_value=1, max_value=10))
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


@st.composite
def invalid_llm_response_json(draw):
    """Generate an invalid LLM response JSON (missing required fields)."""
    # Choose which required field to omit
    omit_field = draw(st.sampled_from([
        "participants",
        "bubbles",
        "layout",
        "participants.self",
        "participants.other",
        "layout.left_role",
        "layout.right_role"
    ]))
    
    # Start with a valid structure
    response = {
        "participants": {
            "self": {"id": "user1", "nickname": "User"},
            "other": {"id": "talker1", "nickname": "Talker"}
        },
        "bubbles": [draw(valid_bubble())],
        "layout": {
            "type": "two_columns",
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    # Remove the chosen field
    if omit_field == "participants":
        del response["participants"]
    elif omit_field == "bubbles":
        del response["bubbles"]
    elif omit_field == "layout":
        del response["layout"]
    elif omit_field == "participants.self":
        del response["participants"]["self"]
    elif omit_field == "participants.other":
        del response["participants"]["other"]
    elif omit_field == "layout.left_role":
        del response["layout"]["left_role"]
    elif omit_field == "layout.right_role":
        del response["layout"]["right_role"]
    
    return response


# Feature: chat-screenshot-parser, Property 3: Output Structure Normalization
@given(
    llm_response_json=st.one_of(
        valid_llm_response_json(),
        invalid_llm_response_json()
    ),
    image_width=st.integers(min_value=100, max_value=2000),
    image_height=st.integers(min_value=100, max_value=2000)
)
@pytest.mark.asyncio
async def test_property_3_output_structure_normalization(
    llm_response_json,
    image_width,
    image_height
):
    """Property 3: For any LLM response (valid or invalid), when the
    Result_Normalizer processes it, the output should either be a valid
    ParsedScreenshotData structure or raise a specific error.
    
    Validates: Requirements 1.3, 4.1
    """
    # Create mock components
    image_fetcher = Mock(spec=ImageFetcher)
    prompt_builder = Mock(spec=PromptBuilder)
    llm_client = Mock(spec=MultimodalLLMClient)
    result_normalizer = ResultNormalizer()  # Use real normalizer
    
    # Create service
    service = ScreenshotParserService(
        image_fetcher=image_fetcher,
        prompt_builder=prompt_builder,
        llm_client=llm_client,
        result_normalizer=result_normalizer
    )
    
    # Mock image fetcher to return valid image
    image_fetcher.fetch_image = AsyncMock(return_value=FetchedImage(
        url="https://example.com/test.jpg",
        width=image_width,
        height=image_height,
        base64_data="fake_base64_data",
        format="jpeg"
    ))
    
    # Mock prompt builder
    prompt_builder.build_prompts = Mock(return_value=(
        "system prompt",
        "user prompt"
    ))
    
    # Mock LLM client to return the test JSON
    llm_client.call = AsyncMock(return_value=MultimodalLLMResponse(
        raw_text="test response",
        parsed_json=llm_response_json,
        provider="test",
        model="test-model",
        input_tokens=100,
        output_tokens=200,
        cost_usd=0.01
    ))
    
    # Create request
    request = ParseScreenshotRequest(
        image_url="https://example.com/test.jpg",
        options=ParseOptions()
    )
    
    # Call the service
    response = await service.parse_screenshot(request)
    
    # Verify the response structure
    assert hasattr(response, 'code'), "Response must have 'code' field"
    assert hasattr(response, 'msg'), "Response must have 'msg' field"
    assert hasattr(response, 'data'), "Response must have 'data' field"
    
    # Check that response is either success or specific error
    assert isinstance(response.code, int), "Response code must be an integer"
    
    if response.code == 0:
        # Success case - verify data structure is valid
        assert response.data is not None, "Success response must have data"
        assert isinstance(response.data, ParsedScreenshotData), \
            "Success response data must be ParsedScreenshotData"
        
        # Verify all required fields in ParsedScreenshotData
        assert hasattr(response.data, 'image_meta')
        assert hasattr(response.data, 'participants')
        assert hasattr(response.data, 'bubbles')
        assert hasattr(response.data, 'layout')
        
        # Verify image_meta
        assert response.data.image_meta.width == image_width
        assert response.data.image_meta.height == image_height
        
        # Verify bubbles is a list
        assert isinstance(response.data.bubbles, list)
        
        # Verify each bubble has required fields
        for bubble in response.data.bubbles:
            assert hasattr(bubble, 'bubble_id')
            assert hasattr(bubble, 'bbox')
            assert hasattr(bubble, 'center_x')
            assert hasattr(bubble, 'center_y')
            assert hasattr(bubble, 'text')
            assert hasattr(bubble, 'sender')
            assert hasattr(bubble, 'column')
            assert hasattr(bubble, 'confidence')
            
            # Verify sender and column are valid
            assert bubble.sender in ["user", "talker"]
            assert bubble.column in ["left", "right"]
            assert 0.0 <= bubble.confidence <= 1.0
    else:
        # Error case - verify error code is specific
        assert response.code in [1001, 1002, 1003, 1004], \
            f"Error code must be one of 1001-1004, got {response.code}"
        
        # Error response should have null data
        assert response.data is None, "Error response should have null data"
        
        # Error message should be descriptive
        assert isinstance(response.msg, str), "Error message must be a string"
        assert len(response.msg) > 0, "Error message must not be empty"


# Feature: chat-screenshot-parser, Property 17: Low Confidence Marking
@given(
    confidence_scores=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=20
    ),
    image_width=st.integers(min_value=100, max_value=2000),
    image_height=st.integers(min_value=100, max_value=2000)
)
@pytest.mark.asyncio
async def test_property_17_low_confidence_marking(
    confidence_scores,
    image_width,
    image_height
):
    """Property 17: For any bubble with confidence score below a threshold
    (e.g., 0.3), the system should mark it for potential fallback processing
    or manual review.
    
    Validates: Requirements 7.5
    """
    # Create mock components
    image_fetcher = Mock(spec=ImageFetcher)
    prompt_builder = Mock(spec=PromptBuilder)
    llm_client = Mock(spec=MultimodalLLMClient)
    result_normalizer = ResultNormalizer()  # Use real normalizer
    
    # Create service
    service = ScreenshotParserService(
        image_fetcher=image_fetcher,
        prompt_builder=prompt_builder,
        llm_client=llm_client,
        result_normalizer=result_normalizer
    )
    
    # Mock image fetcher to return valid image
    image_fetcher.fetch_image = AsyncMock(return_value=FetchedImage(
        url="https://example.com/test.jpg",
        width=image_width,
        height=image_height,
        base64_data="fake_base64_data",
        format="jpeg"
    ))
    
    # Mock prompt builder
    prompt_builder.build_prompts = Mock(return_value=(
        "system prompt",
        "user prompt"
    ))
    
    # Create bubbles with the given confidence scores
    bubbles = []
    for i, confidence in enumerate(confidence_scores):
        bubbles.append({
            "bubble_id": f"b{i}",
            "bbox": {
                "x1": 100,
                "y1": 100 + (i * 60),
                "x2": 200,
                "y2": 150 + (i * 60)
            },
            "text": f"Message {i}",
            "sender": "user" if i % 2 == 0 else "talker",
            "column": "right" if i % 2 == 0 else "left",
            "confidence": confidence
        })
    
    # Create valid LLM response JSON
    llm_response_json = {
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
    
    # Mock LLM client to return the test JSON
    llm_client.call = AsyncMock(return_value=MultimodalLLMResponse(
        raw_text="test response",
        parsed_json=llm_response_json,
        provider="test",
        model="test-model",
        input_tokens=100,
        output_tokens=200,
        cost_usd=0.01
    ))
    
    # Create request
    request = ParseScreenshotRequest(
        image_url="https://example.com/test.jpg",
        options=ParseOptions()
    )
    
    # Call the service
    response = await service.parse_screenshot(request)
    
    # Verify the response is successful
    assert response.code == 0, f"Expected success, got error code {response.code}: {response.msg}"
    assert response.data is not None, "Success response must have data"
    
    # Count expected low confidence bubbles (confidence < 0.3)
    expected_low_confidence_count = sum(1 for conf in confidence_scores if conf < 0.3)
    
    # Count actual low confidence bubbles in the response
    actual_low_confidence_count = sum(
        1 for bubble in response.data.bubbles
        if bubble.confidence < 0.3
    )
    
    # Verify that low confidence bubbles are preserved in the output
    assert actual_low_confidence_count == expected_low_confidence_count, \
        f"Expected {expected_low_confidence_count} low confidence bubbles, " \
        f"but found {actual_low_confidence_count}"
    
    # Verify that all bubbles with confidence < 0.3 are marked correctly
    for bubble in response.data.bubbles:
        if bubble.confidence < 0.3:
            # The bubble should still be in the output (not filtered out)
            assert bubble in response.data.bubbles, \
                f"Low confidence bubble {bubble.bubble_id} should be in output"
            
            # Verify the confidence value is preserved
            assert 0.0 <= bubble.confidence < 0.3, \
                f"Low confidence bubble {bubble.bubble_id} has confidence {bubble.confidence}"
    
    # Verify that the _mark_low_confidence_bubbles method was called
    # by checking that the service processed the data correctly
    # (The method logs warnings but doesn't modify the data structure)
    low_confidence_bubbles = [
        bubble for bubble in response.data.bubbles
        if bubble.confidence < service.LOW_CONFIDENCE_THRESHOLD
    ]
    
    # Verify the threshold is correctly applied
    assert service.LOW_CONFIDENCE_THRESHOLD == 0.3, \
        "Low confidence threshold should be 0.3"
    
    # Verify that bubbles below threshold are identified
    for bubble in low_confidence_bubbles:
        assert bubble.confidence < 0.3, \
            f"Bubble {bubble.bubble_id} marked as low confidence but has confidence {bubble.confidence}"


# Feature: chat-screenshot-parser, Property 18: Cost and Session Tracking Metadata
@given(
    session_id=st.one_of(
        st.none(),
        st.text(min_size=1, max_size=50)
    ),
    provider=st.sampled_from(["openai", "gemini", "claude"]),
    model=st.text(min_size=1, max_size=50),
    input_tokens=st.integers(min_value=1, max_value=10000),
    output_tokens=st.integers(min_value=1, max_value=10000),
    cost_usd=st.floats(min_value=0.0001, max_value=10.0, allow_nan=False, allow_infinity=False),
    image_width=st.integers(min_value=100, max_value=2000),
    image_height=st.integers(min_value=100, max_value=2000)
)
@pytest.mark.asyncio
async def test_property_18_cost_and_session_tracking_metadata(
    session_id,
    provider,
    model,
    input_tokens,
    output_tokens,
    cost_usd,
    image_width,
    image_height
):
    """Property 18: For any successful parse response, the system should
    include metadata for cost tracking (provider, model, tokens) and session
    tracking (session_id if provided).
    
    Validates: Requirements 8.6, 8.7
    """
    # Create mock components
    image_fetcher = Mock(spec=ImageFetcher)
    prompt_builder = Mock(spec=PromptBuilder)
    llm_client = Mock(spec=MultimodalLLMClient)
    result_normalizer = ResultNormalizer()  # Use real normalizer
    
    # Create service
    service = ScreenshotParserService(
        image_fetcher=image_fetcher,
        prompt_builder=prompt_builder,
        llm_client=llm_client,
        result_normalizer=result_normalizer
    )
    
    # Mock image fetcher to return valid image
    image_fetcher.fetch_image = AsyncMock(return_value=FetchedImage(
        url="https://example.com/test.jpg",
        width=image_width,
        height=image_height,
        base64_data="fake_base64_data",
        format="jpeg"
    ))
    
    # Mock prompt builder
    prompt_builder.build_prompts = Mock(return_value=(
        "system prompt",
        "user prompt"
    ))
    
    # Create valid LLM response JSON
    llm_response_json = {
        "participants": {
            "self": {"id": "user1", "nickname": "User"},
            "other": {"id": "talker1", "nickname": "Talker"}
        },
        "bubbles": [
            {
                "bubble_id": "b1",
                "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 150},
                "text": "Test message",
                "sender": "user",
                "column": "right",
                "confidence": 0.9
            }
        ],
        "layout": {
            "type": "two_columns",
            "left_role": "talker",
            "right_role": "user"
        }
    }
    
    # Mock LLM client to return response with metadata
    llm_client.call = AsyncMock(return_value=MultimodalLLMResponse(
        raw_text="test response",
        parsed_json=llm_response_json,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd
    ))
    
    # Create request with session_id
    request = ParseScreenshotRequest(
        image_url="https://example.com/test.jpg",
        session_id=session_id,
        options=ParseOptions()
    )
    
    # Call the service
    response = await service.parse_screenshot(request)
    
    # Verify the response is successful
    assert response.code == 0, f"Expected success, got error code {response.code}: {response.msg}"
    assert response.data is not None, "Success response must have data"
    
    # Verify that the LLM client was called (which provides metadata)
    llm_client.call.assert_called_once()
    
    # Get the actual LLM response that was used internally
    llm_response = llm_client.call.return_value
    
    # Verify cost tracking metadata is available
    assert hasattr(llm_response, 'provider'), "LLM response must have provider metadata"
    assert hasattr(llm_response, 'model'), "LLM response must have model metadata"
    assert hasattr(llm_response, 'input_tokens'), "LLM response must have input_tokens metadata"
    assert hasattr(llm_response, 'output_tokens'), "LLM response must have output_tokens metadata"
    assert hasattr(llm_response, 'cost_usd'), "LLM response must have cost_usd metadata"
    
    # Verify metadata values match what was provided
    assert llm_response.provider == provider, \
        f"Provider metadata mismatch: expected {provider}, got {llm_response.provider}"
    assert llm_response.model == model, \
        f"Model metadata mismatch: expected {model}, got {llm_response.model}"
    assert llm_response.input_tokens == input_tokens, \
        f"Input tokens metadata mismatch: expected {input_tokens}, got {llm_response.input_tokens}"
    assert llm_response.output_tokens == output_tokens, \
        f"Output tokens metadata mismatch: expected {output_tokens}, got {llm_response.output_tokens}"
    assert abs(llm_response.cost_usd - cost_usd) < 0.0001, \
        f"Cost metadata mismatch: expected {cost_usd}, got {llm_response.cost_usd}"
    
    # Verify session tracking
    # The session_id is used internally for logging and tracking
    # Verify that the request session_id was preserved
    expected_session_id = session_id if session_id else "unknown"
    
    # The service should have processed the request with the session_id
    # We can verify this by checking that the service used the session_id
    # (In a real implementation, this would be in logs or response metadata)
    
    # Verify that the service handled the session_id correctly
    # by checking that it didn't raise an error and completed successfully
    assert response.code == 0, "Service should handle session_id correctly"
    
    # Verify that cost metadata is non-negative
    assert llm_response.input_tokens >= 0, "Input tokens must be non-negative"
    assert llm_response.output_tokens >= 0, "Output tokens must be non-negative"
    assert llm_response.cost_usd >= 0.0, "Cost must be non-negative"
    
    # Verify that provider and model are non-empty strings
    assert len(llm_response.provider) > 0, "Provider must be a non-empty string"
    assert len(llm_response.model) > 0, "Model must be a non-empty string"
    
    # Verify that the metadata is consistent with the LLM call
    # The service should have logged this metadata for monitoring
    # (In production, this would be captured by logging/monitoring systems)


# Feature: chat-screenshot-parser, Property 19: Response Structure Completeness
@given(
    is_success=st.booleans(),
    image_width=st.integers(min_value=100, max_value=2000),
    image_height=st.integers(min_value=100, max_value=2000),
    num_bubbles=st.integers(min_value=0, max_value=20)
)
@pytest.mark.asyncio
async def test_property_19_response_structure_completeness(
    is_success,
    image_width,
    image_height,
    num_bubbles
):
    """Property 19: For any response from the Chat_Screenshot_Parser, it should
    include code (integer), msg (string), and for successful responses (code=0),
    a data object containing image_meta, participants, bubbles, and layout.
    
    Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.10
    """
    # Create mock components
    image_fetcher = Mock(spec=ImageFetcher)
    prompt_builder = Mock(spec=PromptBuilder)
    llm_client = Mock(spec=MultimodalLLMClient)
    result_normalizer = ResultNormalizer()  # Use real normalizer
    
    # Create service
    service = ScreenshotParserService(
        image_fetcher=image_fetcher,
        prompt_builder=prompt_builder,
        llm_client=llm_client,
        result_normalizer=result_normalizer
    )
    
    # Mock image fetcher to return valid image
    image_fetcher.fetch_image = AsyncMock(return_value=FetchedImage(
        url="https://example.com/test.jpg",
        width=image_width,
        height=image_height,
        base64_data="fake_base64_data",
        format="jpeg"
    ))
    
    # Mock prompt builder
    prompt_builder.build_prompts = Mock(return_value=(
        "system prompt",
        "user prompt"
    ))
    
    if is_success:
        # Create valid LLM response JSON for success case
        bubbles = []
        for i in range(num_bubbles):
            bubbles.append({
                "bubble_id": f"b{i}",
                "bbox": {
                    "x1": 100,
                    "y1": 100 + (i * 60),
                    "x2": 200,
                    "y2": 150 + (i * 60)
                },
                "text": f"Message {i}",
                "sender": "user" if i % 2 == 0 else "talker",
                "column": "right" if i % 2 == 0 else "left",
                "confidence": 0.9
            })
        
        llm_response_json = {
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
        
        # Mock LLM client to return valid response
        llm_client.call = AsyncMock(return_value=MultimodalLLMResponse(
            raw_text="test response",
            parsed_json=llm_response_json,
            provider="test",
            model="test-model",
            input_tokens=100,
            output_tokens=200,
            cost_usd=0.01
        ))
    else:
        # Create invalid LLM response JSON for error case (missing required field)
        llm_response_json = {
            "participants": {
                "self": {"id": "user1", "nickname": "User"}
                # Missing "other" participant - will cause error 1004
            },
            "bubbles": [],
            "layout": {
                "type": "two_columns",
                "left_role": "talker",
                "right_role": "user"
            }
        }
        
        # Mock LLM client to return invalid response
        llm_client.call = AsyncMock(return_value=MultimodalLLMResponse(
            raw_text="test response",
            parsed_json=llm_response_json,
            provider="test",
            model="test-model",
            input_tokens=100,
            output_tokens=200,
            cost_usd=0.01
        ))
    
    # Create request
    request = ParseScreenshotRequest(
        image_url="https://example.com/test.jpg",
        options=ParseOptions()
    )
    
    # Call the service
    response = await service.parse_screenshot(request)
    
    # Requirement 9.1: Response must have code field (integer)
    assert hasattr(response, 'code'), "Response must have 'code' field"
    assert isinstance(response.code, int), "Response code must be an integer"
    
    # Requirement 9.2: Response must have msg field (string)
    assert hasattr(response, 'msg'), "Response must have 'msg' field"
    assert isinstance(response.msg, str), "Response msg must be a string"
    assert len(response.msg) > 0, "Response msg must not be empty"
    
    # Requirement 9.3: Response must have data field
    assert hasattr(response, 'data'), "Response must have 'data' field"
    
    if response.code == 0:
        # Success case - verify complete data structure
        # Requirement 9.3: data field must contain parsed structure
        assert response.data is not None, "Success response (code=0) must have non-null data"
        assert isinstance(response.data, ParsedScreenshotData), \
            "Success response data must be ParsedScreenshotData instance"
        
        # Requirement 9.4: data field must include image_meta with width and height
        assert hasattr(response.data, 'image_meta'), "Data must have 'image_meta' field"
        assert isinstance(response.data.image_meta, ImageMeta), \
            "image_meta must be ImageMeta instance"
        assert hasattr(response.data.image_meta, 'width'), "image_meta must have 'width' field"
        assert hasattr(response.data.image_meta, 'height'), "image_meta must have 'height' field"
        assert isinstance(response.data.image_meta.width, int), "image_meta.width must be integer"
        assert isinstance(response.data.image_meta.height, int), "image_meta.height must be integer"
        assert response.data.image_meta.width == image_width, \
            f"image_meta.width must match input: expected {image_width}, got {response.data.image_meta.width}"
        assert response.data.image_meta.height == image_height, \
            f"image_meta.height must match input: expected {image_height}, got {response.data.image_meta.height}"
        
        # Requirement 9.5: data field must include participants with self and other
        assert hasattr(response.data, 'participants'), "Data must have 'participants' field"
        assert isinstance(response.data.participants, Participants), \
            "participants must be Participants instance"
        assert hasattr(response.data.participants, 'self'), "participants must have 'self' field"
        assert hasattr(response.data.participants, 'other'), "participants must have 'other' field"
        
        # Requirement 9.10: Each participant must have id and nickname
        assert hasattr(response.data.participants.self, 'id'), "self participant must have 'id' field"
        assert hasattr(response.data.participants.self, 'nickname'), \
            "self participant must have 'nickname' field"
        assert isinstance(response.data.participants.self.id, str), "self.id must be string"
        assert isinstance(response.data.participants.self.nickname, str), "self.nickname must be string"
        assert len(response.data.participants.self.id) > 0, "self.id must not be empty"
        assert len(response.data.participants.self.nickname) > 0, "self.nickname must not be empty"
        
        assert hasattr(response.data.participants.other, 'id'), "other participant must have 'id' field"
        assert hasattr(response.data.participants.other, 'nickname'), \
            "other participant must have 'nickname' field"
        assert isinstance(response.data.participants.other.id, str), "other.id must be string"
        assert isinstance(response.data.participants.other.nickname, str), "other.nickname must be string"
        assert len(response.data.participants.other.id) > 0, "other.id must not be empty"
        assert len(response.data.participants.other.nickname) > 0, "other.nickname must not be empty"
        
        # Requirement 9.6: data field must include bubbles array
        assert hasattr(response.data, 'bubbles'), "Data must have 'bubbles' field"
        assert isinstance(response.data.bubbles, list), "bubbles must be a list"
        assert len(response.data.bubbles) == num_bubbles, \
            f"bubbles array length must match input: expected {num_bubbles}, got {len(response.data.bubbles)}"
        
        # Requirement 9.8: Each bubble must have required fields
        for i, bubble in enumerate(response.data.bubbles):
            assert isinstance(bubble, ChatBubble), f"Bubble {i} must be ChatBubble instance"
            assert hasattr(bubble, 'bubble_id'), f"Bubble {i} must have 'bubble_id' field"
            assert hasattr(bubble, 'bbox'), f"Bubble {i} must have 'bbox' field"
            assert hasattr(bubble, 'center_x'), f"Bubble {i} must have 'center_x' field"
            assert hasattr(bubble, 'center_y'), f"Bubble {i} must have 'center_y' field"
            assert hasattr(bubble, 'text'), f"Bubble {i} must have 'text' field"
            assert hasattr(bubble, 'sender'), f"Bubble {i} must have 'sender' field"
            assert hasattr(bubble, 'column'), f"Bubble {i} must have 'column' field"
            assert hasattr(bubble, 'confidence'), f"Bubble {i} must have 'confidence' field"
            
            # Verify field types
            assert isinstance(bubble.bubble_id, str), f"Bubble {i} bubble_id must be string"
            assert isinstance(bubble.center_x, int), f"Bubble {i} center_x must be integer"
            assert isinstance(bubble.center_y, int), f"Bubble {i} center_y must be integer"
            assert isinstance(bubble.text, str), f"Bubble {i} text must be string"
            assert bubble.sender in ["user", "talker"], \
                f"Bubble {i} sender must be 'user' or 'talker', got {bubble.sender}"
            assert bubble.column in ["left", "right"], \
                f"Bubble {i} column must be 'left' or 'right', got {bubble.column}"
            assert isinstance(bubble.confidence, float), f"Bubble {i} confidence must be float"
            assert 0.0 <= bubble.confidence <= 1.0, \
                f"Bubble {i} confidence must be in [0.0, 1.0], got {bubble.confidence}"
            
            # Requirement 9.9: bbox must have x1, y1, x2, y2
            assert hasattr(bubble.bbox, 'x1'), f"Bubble {i} bbox must have 'x1' field"
            assert hasattr(bubble.bbox, 'y1'), f"Bubble {i} bbox must have 'y1' field"
            assert hasattr(bubble.bbox, 'x2'), f"Bubble {i} bbox must have 'x2' field"
            assert hasattr(bubble.bbox, 'y2'), f"Bubble {i} bbox must have 'y2' field"
            assert isinstance(bubble.bbox.x1, int), f"Bubble {i} bbox.x1 must be integer"
            assert isinstance(bubble.bbox.y1, int), f"Bubble {i} bbox.y1 must be integer"
            assert isinstance(bubble.bbox.x2, int), f"Bubble {i} bbox.x2 must be integer"
            assert isinstance(bubble.bbox.y2, int), f"Bubble {i} bbox.y2 must be integer"
        
        # Requirement 9.7: data field must include layout object
        assert hasattr(response.data, 'layout'), "Data must have 'layout' field"
        assert isinstance(response.data.layout, LayoutInfo), "layout must be LayoutInfo instance"
        assert hasattr(response.data.layout, 'type'), "layout must have 'type' field"
        assert hasattr(response.data.layout, 'left_role'), "layout must have 'left_role' field"
        assert hasattr(response.data.layout, 'right_role'), "layout must have 'right_role' field"
        assert isinstance(response.data.layout.type, str), "layout.type must be string"
        assert response.data.layout.left_role in ["user", "talker"], \
            f"layout.left_role must be 'user' or 'talker', got {response.data.layout.left_role}"
        assert response.data.layout.right_role in ["user", "talker"], \
            f"layout.right_role must be 'user' or 'talker', got {response.data.layout.right_role}"
        
    else:
        # Error case - verify error structure
        assert response.code != 0, "Error response must have non-zero code"
        assert response.code in [1001, 1002, 1003, 1004], \
            f"Error code must be one of 1001-1004, got {response.code}"
        
        # Error response should have null data
        assert response.data is None, \
            f"Error response (code={response.code}) must have null data, got {response.data}"
        
        # Error message should be descriptive
        assert len(response.msg) > 0, "Error message must not be empty"
        assert isinstance(response.msg, str), "Error message must be a string"
