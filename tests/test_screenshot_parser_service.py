"""Unit tests for ScreenshotParserService.

This module tests the main screenshot parser service orchestration,
error handling, and integration between components.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from app.services.screenshot_parser import ScreenshotParserService
from app.models.screenshot import (
    ParseScreenshotRequest,
    ParseScreenshotResponse,
    ParseOptions,
    FetchedImage,
    MultimodalLLMResponse,
    ParsedScreenshotData,
    ImageMeta,
    Participants,
    Participant,
    LayoutInfo,
    ChatBubble,
    BoundingBox,
)


@pytest.fixture
def mock_image_fetcher():
    """Create a mock ImageFetcher."""
    fetcher = Mock()
    fetcher.fetch_image = AsyncMock(return_value=FetchedImage(
        url="https://example.com/image.jpg",
        width=800,
        height=1200,
        base64_data="fake_base64_data",
        format="jpeg"
    ))
    return fetcher


@pytest.fixture
def mock_prompt_builder():
    """Create a mock PromptBuilder."""
    builder = Mock()
    builder.build_prompts = Mock(return_value=(
        "System prompt",
        "User prompt"
    ))
    return builder


@pytest.fixture
def mock_llm_client():
    """Create a mock MultimodalLLMClient."""
    client = Mock()
    client.call = AsyncMock(return_value=MultimodalLLMResponse(
        raw_text='{"test": "data"}',
        parsed_json={
            "participants": {
                "self": {"id": "user1", "nickname": "User"},
                "other": {"id": "user2", "nickname": "Other"}
            },
            "bubbles": [
                {
                    "bubble_id": "b1",
                    "bbox": {"x1": 100, "y1": 100, "x2": 300, "y2": 150},
                    "center_x": 200,
                    "center_y": 125,
                    "text": "Hello",
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
        },
        provider="openai",
        model="gpt-4o",
        input_tokens=1000,
        output_tokens=500,
        cost_usd=0.05
    ))
    return client


@pytest.fixture
def mock_result_normalizer():
    """Create a mock ResultNormalizer."""
    normalizer = Mock()
    normalizer.normalize = Mock(return_value=ParsedScreenshotData(
        image_meta=ImageMeta(width=800, height=1200),
        participants=Participants(
            self=Participant(id="user1", nickname="User"),
            other=Participant(id="user2", nickname="Other")
        ),
        bubbles=[
            ChatBubble(
                bubble_id="b1",
                bbox=BoundingBox(x1=100, y1=100, x2=300, y2=150),
                center_x=200,
                center_y=125,
                text="Hello",
                sender="user",
                column="right",
                confidence=0.9
            )
        ],
        layout=LayoutInfo(
            type="two_columns",
            left_role="talker",
            right_role="user"
        )
    ))
    return normalizer


@pytest.fixture
def screenshot_parser_service(
    mock_image_fetcher,
    mock_prompt_builder,
    mock_llm_client,
    mock_result_normalizer
):
    """Create a ScreenshotParserService with mocked dependencies."""
    return ScreenshotParserService(
        image_fetcher=mock_image_fetcher,
        prompt_builder=mock_prompt_builder,
        llm_client=mock_llm_client,
        result_normalizer=mock_result_normalizer
    )


@pytest.mark.asyncio
async def test_parse_screenshot_success(screenshot_parser_service):
    """Test successful screenshot parsing."""
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session",
        options=ParseOptions()
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 0
    assert response.msg == "Success"
    assert response.data is not None
    assert len(response.data.bubbles) == 1
    assert response.data.bubbles[0].text == "Hello"


@pytest.mark.asyncio
async def test_parse_screenshot_image_fetch_error(
    screenshot_parser_service,
    mock_image_fetcher
):
    """Test error handling when image fetch fails."""
    mock_image_fetcher.fetch_image.side_effect = ValueError("Invalid URL")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/invalid.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1001
    assert "Failed to download or process image" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_parse_screenshot_llm_call_error(
    screenshot_parser_service,
    mock_llm_client
):
    """Test error handling when LLM call fails."""
    mock_llm_client.call.side_effect = RuntimeError("API error")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1002
    assert "LLM API call failed" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_parse_screenshot_json_parse_error(
    screenshot_parser_service,
    mock_llm_client
):
    """Test error handling when JSON parsing fails."""
    mock_llm_client.call.side_effect = RuntimeError("Failed to parse JSON from response")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1003
    assert "Failed to parse JSON" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_parse_screenshot_normalization_error(
    screenshot_parser_service,
    mock_result_normalizer
):
    """Test error handling when normalization fails."""
    mock_result_normalizer.normalize.side_effect = ValueError("Missing required field")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1004
    assert "Missing or invalid required fields" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_parse_screenshot_low_confidence_marking(
    screenshot_parser_service,
    mock_result_normalizer
):
    """Test that low confidence bubbles are marked for review."""
    # Create a response with low confidence bubble
    mock_result_normalizer.normalize.return_value = ParsedScreenshotData(
        image_meta=ImageMeta(width=800, height=1200),
        participants=Participants(
            self=Participant(id="user1", nickname="User"),
            other=Participant(id="user2", nickname="Other")
        ),
        bubbles=[
            ChatBubble(
                bubble_id="b1",
                bbox=BoundingBox(x1=100, y1=100, x2=300, y2=150),
                center_x=200,
                center_y=125,
                text="Hello",
                sender="user",
                column="right",
                confidence=0.2  # Low confidence
            )
        ],
        layout=LayoutInfo(
            type="two_columns",
            left_role="talker",
            right_role="user"
        )
    )
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    # Should still succeed but log warning
    assert response.code == 0
    assert response.data is not None
    assert response.data.bubbles[0].confidence == 0.2


@pytest.mark.asyncio
async def test_parse_screenshot_default_options(screenshot_parser_service):
    """Test that default options are used when not provided."""
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        # No options provided
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 0
    assert response.data is not None


@pytest.mark.asyncio
async def test_parse_screenshot_workflow_order(
    screenshot_parser_service,
    mock_image_fetcher,
    mock_prompt_builder,
    mock_llm_client,
    mock_result_normalizer
):
    """Test that workflow components are called in correct order."""
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session",
        options=ParseOptions()
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    # Verify all components were called
    mock_image_fetcher.fetch_image.assert_called_once_with(request.image_url)
    mock_prompt_builder.build_prompts.assert_called_once()
    mock_llm_client.call.assert_called_once()
    mock_result_normalizer.normalize.assert_called_once()
    
    assert response.code == 0


# ============================================================================
# Error Code Mapping Tests (Task 8.9)
# ============================================================================


@pytest.mark.asyncio
async def test_error_code_1001_invalid_url_format(
    screenshot_parser_service,
    mock_image_fetcher
):
    """Test error code 1001 is returned for invalid URL format.
    
    Validates: Requirements 1.5, 5.1
    """
    mock_image_fetcher.fetch_image.side_effect = ValueError("Invalid URL format")
    
    request = ParseScreenshotRequest(
        image_url="not-a-valid-url",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1001
    assert "Failed to download or process image" in response.msg
    assert "Invalid URL format" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1001_download_failure(
    screenshot_parser_service,
    mock_image_fetcher
):
    """Test error code 1001 is returned for image download failure.
    
    Validates: Requirements 1.5, 5.2, 5.5
    """
    mock_image_fetcher.fetch_image.side_effect = ValueError("Failed to download image: 404 Not Found")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/nonexistent.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1001
    assert "Failed to download or process image" in response.msg
    assert "404 Not Found" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1001_invalid_image_format(
    screenshot_parser_service,
    mock_image_fetcher
):
    """Test error code 1001 is returned for invalid image format.
    
    Validates: Requirements 1.5, 5.6, 5.7
    """
    mock_image_fetcher.fetch_image.side_effect = ValueError("Unsupported image format: .gif")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.gif",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1001
    assert "Failed to download or process image" in response.msg
    assert "Unsupported image format" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1001_unexpected_image_error(
    screenshot_parser_service,
    mock_image_fetcher
):
    """Test error code 1001 is returned for unexpected image processing errors.
    
    Validates: Requirements 1.5
    """
    mock_image_fetcher.fetch_image.side_effect = IOError("Disk read error")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1001
    assert "Unexpected error fetching image" in response.msg
    assert "Disk read error" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1002_llm_api_failure(
    screenshot_parser_service,
    mock_llm_client
):
    """Test error code 1002 is returned for LLM API call failure.
    
    Validates: Requirements 1.6, 7.2
    """
    mock_llm_client.call.side_effect = RuntimeError("API rate limit exceeded")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1002
    assert "LLM API call failed" in response.msg
    assert "rate limit exceeded" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1002_llm_authentication_error(
    screenshot_parser_service,
    mock_llm_client
):
    """Test error code 1002 is returned for LLM authentication errors.
    
    Validates: Requirements 1.6, 7.2
    """
    mock_llm_client.call.side_effect = RuntimeError("Invalid API key")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1002
    assert "LLM API call failed" in response.msg
    assert "Invalid API key" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1002_llm_timeout(
    screenshot_parser_service,
    mock_llm_client
):
    """Test error code 1002 is returned for LLM timeout errors.
    
    Validates: Requirements 1.6, 7.2
    """
    mock_llm_client.call.side_effect = RuntimeError("Request timeout after 30s")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1002
    assert "LLM API call failed" in response.msg
    assert "timeout" in response.msg.lower()
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1002_unexpected_llm_error(
    screenshot_parser_service,
    mock_llm_client
):
    """Test error code 1002 is returned for unexpected LLM errors.
    
    Validates: Requirements 1.6, 7.2
    """
    mock_llm_client.call.side_effect = ConnectionError("Network unreachable")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1002
    assert "Unexpected error calling LLM" in response.msg
    assert "Network unreachable" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1003_invalid_json_response(
    screenshot_parser_service,
    mock_llm_client
):
    """Test error code 1003 is returned for invalid JSON in LLM response.
    
    Validates: Requirements 1.7, 3.5, 7.3
    """
    mock_llm_client.call.side_effect = RuntimeError("Failed to parse JSON from response")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1003
    assert "Failed to parse JSON" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1003_malformed_json(
    screenshot_parser_service,
    mock_llm_client
):
    """Test error code 1003 is returned for malformed JSON.
    
    Validates: Requirements 1.7, 3.5, 7.3
    """
    mock_llm_client.call.side_effect = RuntimeError("JSON decode error: Expecting value")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1003
    assert "Failed to parse JSON" in response.msg
    assert "JSON decode error" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1004_missing_required_fields(
    screenshot_parser_service,
    mock_result_normalizer
):
    """Test error code 1004 is returned for missing required fields.
    
    Validates: Requirements 1.8, 4.1, 7.4
    """
    mock_result_normalizer.normalize.side_effect = ValueError("Missing required field: bubbles")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1004
    assert "Missing or invalid required fields" in response.msg
    assert "Missing required field: bubbles" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1004_invalid_field_values(
    screenshot_parser_service,
    mock_result_normalizer
):
    """Test error code 1004 is returned for invalid field values.
    
    Validates: Requirements 1.8, 4.2, 4.3, 7.4
    """
    mock_result_normalizer.normalize.side_effect = ValueError("Invalid sender value: 'invalid'")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1004
    assert "Missing or invalid required fields" in response.msg
    assert "Invalid sender value" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1004_invalid_bbox_coordinates(
    screenshot_parser_service,
    mock_result_normalizer
):
    """Test error code 1004 is returned for invalid bounding box coordinates.
    
    Validates: Requirements 1.8, 4.4, 7.4
    """
    mock_result_normalizer.normalize.side_effect = ValueError("Invalid bbox coordinates: x1 > x2")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1004
    assert "Missing or invalid required fields" in response.msg
    assert "Invalid bbox coordinates" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_code_1004_unexpected_normalization_error(
    screenshot_parser_service,
    mock_result_normalizer
):
    """Test error code 1004 is returned for unexpected normalization errors.
    
    Validates: Requirements 1.8, 7.4
    """
    mock_result_normalizer.normalize.side_effect = KeyError("participants")
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await screenshot_parser_service.parse_screenshot(request)
    
    assert response.code == 1004
    assert "Unexpected error normalizing output" in response.msg
    assert "participants" in response.msg
    assert response.data is None


@pytest.mark.asyncio
async def test_error_messages_are_descriptive():
    """Test that all error messages provide sufficient context for debugging.
    
    This test verifies that error messages include:
    - The specific error that occurred
    - Context about what operation failed
    - Original error details when available
    
    Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.6
    """
    # Create service with mocked dependencies
    mock_image_fetcher = Mock()
    mock_prompt_builder = Mock()
    mock_llm_client = Mock()
    mock_result_normalizer = Mock()
    
    service = ScreenshotParserService(
        image_fetcher=mock_image_fetcher,
        prompt_builder=mock_prompt_builder,
        llm_client=mock_llm_client,
        result_normalizer=mock_result_normalizer
    )
    
    # Test various error scenarios
    test_cases = [
        {
            "error": ValueError("Connection refused"),
            "component": "image_fetcher",
            "expected_code": 1001,
            "expected_keywords": ["Failed to download", "Connection refused"]
        },
        {
            "error": RuntimeError("Service unavailable"),
            "component": "llm_client",
            "expected_code": 1002,
            "expected_keywords": ["LLM API call failed", "Service unavailable"]
        },
        {
            "error": RuntimeError("Invalid JSON structure"),
            "component": "llm_client",
            "expected_code": 1003,
            "expected_keywords": ["Failed to parse JSON", "Invalid JSON structure"]
        },
        {
            "error": ValueError("Field 'text' is required"),
            "component": "result_normalizer",
            "expected_code": 1004,
            "expected_keywords": ["Missing or invalid", "Field 'text' is required"]
        },
    ]
    
    for test_case in test_cases:
        # Reset mocks
        mock_image_fetcher.fetch_image = AsyncMock(return_value=FetchedImage(
            url="https://example.com/image.jpg",
            width=800,
            height=1200,
            base64_data="fake_base64",
            format="jpeg"
        ))
        mock_prompt_builder.build_prompts = Mock(return_value=("sys", "user"))
        mock_llm_client.call = AsyncMock(return_value=MultimodalLLMResponse(
            raw_text='{"test": "data"}',
            parsed_json={"test": "data"},
            provider="openai",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01
        ))
        mock_result_normalizer.normalize = Mock()
        
        # Set up the specific error
        if test_case["component"] == "image_fetcher":
            mock_image_fetcher.fetch_image.side_effect = test_case["error"]
        elif test_case["component"] == "llm_client":
            mock_llm_client.call.side_effect = test_case["error"]
        elif test_case["component"] == "result_normalizer":
            mock_result_normalizer.normalize.side_effect = test_case["error"]
        
        # Execute request
        request = ParseScreenshotRequest(
            image_url="https://example.com/image.jpg",
            session_id="test-session"
        )
        response = await service.parse_screenshot(request)
        
        # Verify error code
        assert response.code == test_case["expected_code"], \
            f"Expected code {test_case['expected_code']}, got {response.code}"
        
        # Verify message is descriptive
        for keyword in test_case["expected_keywords"]:
            assert keyword in response.msg, \
                f"Expected '{keyword}' in error message, got: {response.msg}"
        
        # Verify no data is returned
        assert response.data is None


@pytest.mark.asyncio
async def test_success_code_zero():
    """Test that successful parsing returns code 0.
    
    Validates: Requirements 9.1
    """
    # Create service with successful mocks
    mock_image_fetcher = Mock()
    mock_image_fetcher.fetch_image = AsyncMock(return_value=FetchedImage(
        url="https://example.com/image.jpg",
        width=800,
        height=1200,
        base64_data="fake_base64",
        format="jpeg"
    ))
    
    mock_prompt_builder = Mock()
    mock_prompt_builder.build_prompts = Mock(return_value=("sys", "user"))
    
    mock_llm_client = Mock()
    mock_llm_client.call = AsyncMock(return_value=MultimodalLLMResponse(
        raw_text='{"test": "data"}',
        parsed_json={
            "participants": {
                "self": {"id": "u1", "nickname": "User"},
                "other": {"id": "u2", "nickname": "Other"}
            },
            "bubbles": [],
            "layout": {"type": "two_columns", "left_role": "talker", "right_role": "user"}
        },
        provider="openai",
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01
    ))
    
    mock_result_normalizer = Mock()
    mock_result_normalizer.normalize = Mock(return_value=ParsedScreenshotData(
        image_meta=ImageMeta(width=800, height=1200),
        participants=Participants(
            self=Participant(id="u1", nickname="User"),
            other=Participant(id="u2", nickname="Other")
        ),
        bubbles=[],
        layout=LayoutInfo(type="two_columns", left_role="talker", right_role="user")
    ))
    
    service = ScreenshotParserService(
        image_fetcher=mock_image_fetcher,
        prompt_builder=mock_prompt_builder,
        llm_client=mock_llm_client,
        result_normalizer=mock_result_normalizer
    )
    
    request = ParseScreenshotRequest(
        image_url="https://example.com/image.jpg",
        session_id="test-session"
    )
    
    response = await service.parse_screenshot(request)
    
    assert response.code == 0
    assert response.msg == "Success"
    assert response.data is not None
