"""Unit tests for screenshot parsing API endpoint.

This module tests the FastAPI endpoint for screenshot parsing,
including request validation, error handling, and response formatting.

Task 9.5: Write unit tests for API endpoint
- Test successful parse request
- Test validation errors
- Test error responses with correct status codes
"""

import pytest
from unittest.mock import AsyncMock, Mock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.screenshot import router
from app.models.screenshot import (
    ParseScreenshotRequest,
    ParseScreenshotResponse,
    ParsedScreenshotData,
    ImageMeta,
    Participants,
    Participant,
    LayoutInfo,
    ChatBubble,
    BoundingBox,
)
from app.services.screenshot_parser import ScreenshotParserService


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_screenshot_parser_service():
    """Create a mock ScreenshotParserService."""
    service = Mock(spec=ScreenshotParserService)
    
    # Default successful response
    service.parse_screenshot = AsyncMock(return_value=ParseScreenshotResponse(
        code=0,
        msg="Success",
        data=ParsedScreenshotData(
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
        )
    ))
    
    return service


@pytest.fixture
def test_app(mock_screenshot_parser_service):
    """Create a test FastAPI app with the screenshot router."""
    app = FastAPI()
    
    # Override the dependency to use our mock
    from app.core.dependencies import get_screenshot_parser
    
    def override_get_screenshot_parser():
        return mock_screenshot_parser_service
    
    app.dependency_overrides[get_screenshot_parser] = override_get_screenshot_parser
    app.include_router(router, prefix="/api/v1")
    
    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


# ============================================================================
# Successful Parse Request Tests
# ============================================================================


def test_parse_screenshot_success(client, mock_screenshot_parser_service):
    """Test successful screenshot parsing request.
    
    Validates: Requirements 1.1, 1.2, 1.3, 1.4
    """
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg",
            "session_id": "test-session-123",
            "options": {
                "need_nickname": True,
                "need_sender": True,
                "force_two_columns": True,
                "app_type": "wechat"
            }
        }
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["code"] == 0
    assert data["msg"] == "Success"
    assert data["data"] is not None
    assert data["data"]["image_meta"]["width"] == 800
    assert data["data"]["image_meta"]["height"] == 1200
    assert len(data["data"]["bubbles"]) == 1
    assert data["data"]["bubbles"][0]["text"] == "Hello"
    
    # Verify service was called with correct request
    mock_screenshot_parser_service.parse_screenshot.assert_called_once()
    call_args = mock_screenshot_parser_service.parse_screenshot.call_args[0][0]
    assert call_args.image_url == "https://example.com/screenshot.jpg"
    assert call_args.session_id == "test-session-123"
    assert call_args.options.app_type == "wechat"


def test_parse_screenshot_minimal_request(client, mock_screenshot_parser_service):
    """Test successful parsing with minimal required fields.
    
    Validates: Requirements 1.1
    """
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg"
        }
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["code"] == 0
    assert data["msg"] == "Success"
    assert data["data"] is not None
    
    # Verify service was called
    mock_screenshot_parser_service.parse_screenshot.assert_called_once()
    call_args = mock_screenshot_parser_service.parse_screenshot.call_args[0][0]
    assert call_args.image_url == "https://example.com/screenshot.jpg"
    assert call_args.session_id is None
    assert call_args.options is None


def test_parse_screenshot_with_session_id_only(client, mock_screenshot_parser_service):
    """Test parsing with session_id but no options.
    
    Validates: Requirements 6.1
    """
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg",
            "session_id": "session-456"
        }
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["code"] == 0
    
    # Verify session_id was passed
    call_args = mock_screenshot_parser_service.parse_screenshot.call_args[0][0]
    assert call_args.session_id == "session-456"


def test_parse_screenshot_with_partial_options(client, mock_screenshot_parser_service):
    """Test parsing with partial options (using defaults for others).
    
    Validates: Requirements 6.2, 6.3, 6.4, 6.5
    """
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg",
            "options": {
                "app_type": "line"
            }
        }
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["code"] == 0
    
    # Verify options were passed
    call_args = mock_screenshot_parser_service.parse_screenshot.call_args[0][0]
    assert call_args.options.app_type == "line"
    # Other options should use defaults
    assert call_args.options.need_nickname is True
    assert call_args.options.need_sender is True
    assert call_args.options.force_two_columns is True


# ============================================================================
# Validation Error Tests
# ============================================================================


def test_parse_screenshot_missing_image_url(client):
    """Test validation error when image_url is missing.
    
    Validates: Requirements 6.1
    """
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "session_id": "test-session"
        }
    )
    
    assert response.status_code == 422  # FastAPI validation error
    
    data = response.json()
    assert "detail" in data
    # Check that the error mentions image_url
    error_details = str(data["detail"])
    assert "image_url" in error_details.lower()


def test_parse_screenshot_empty_image_url(client):
    """Test validation error when image_url is empty.
    
    Validates: Requirements 6.1
    """
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": ""
        }
    )
    
    assert response.status_code == 422  # FastAPI validation error
    
    data = response.json()
    assert "detail" in data


def test_parse_screenshot_invalid_app_type(client):
    """Test validation error when app_type is invalid.
    
    Validates: Requirements 6.5
    """
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg",
            "options": {
                "app_type": "invalid_app"
            }
        }
    )
    
    assert response.status_code == 422  # FastAPI validation error
    
    data = response.json()
    assert "detail" in data
    # Check that the error mentions app_type
    error_details = str(data["detail"])
    assert "app_type" in error_details.lower()


def test_parse_screenshot_invalid_option_types(client):
    """Test validation error when option types are wrong.
    
    Validates: Requirements 6.2, 6.3, 6.4
    """
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg",
            "options": {
                "need_nickname": "not_a_boolean",
                "need_sender": "also_not_a_boolean",
                "force_two_columns": "still_not_a_boolean"
            }
        }
    )
    
    assert response.status_code == 422  # FastAPI validation error
    
    data = response.json()
    assert "detail" in data


def test_parse_screenshot_invalid_json(client):
    """Test validation error when request body is not valid JSON."""
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        data="not valid json",
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 422


# ============================================================================
# Error Response Tests (Service Errors)
# ============================================================================


def test_parse_screenshot_image_download_error(client, mock_screenshot_parser_service):
    """Test error response when image download fails (error code 1001).
    
    Validates: Requirements 1.5, 7.1
    """
    # Configure mock to return error response
    mock_screenshot_parser_service.parse_screenshot.return_value = ParseScreenshotResponse(
        code=1001,
        msg="Failed to download or process image: Invalid URL format",
        data=None
    )
    
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/invalid.jpg"
        }
    )
    
    assert response.status_code == 200  # API returns 200 with error in body
    
    data = response.json()
    assert data["code"] == 1001
    assert "Failed to download or process image" in data["msg"]
    assert data["data"] is None


def test_parse_screenshot_llm_call_error(client, mock_screenshot_parser_service):
    """Test error response when LLM call fails (error code 1002).
    
    Validates: Requirements 1.6, 7.2
    """
    # Configure mock to return error response
    mock_screenshot_parser_service.parse_screenshot.return_value = ParseScreenshotResponse(
        code=1002,
        msg="LLM API call failed: Rate limit exceeded",
        data=None
    )
    
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg"
        }
    )
    
    assert response.status_code == 200  # API returns 200 with error in body
    
    data = response.json()
    assert data["code"] == 1002
    assert "LLM API call failed" in data["msg"]
    assert data["data"] is None


def test_parse_screenshot_json_parse_error(client, mock_screenshot_parser_service):
    """Test error response when JSON parsing fails (error code 1003).
    
    Validates: Requirements 1.7, 7.3
    """
    # Configure mock to return error response
    mock_screenshot_parser_service.parse_screenshot.return_value = ParseScreenshotResponse(
        code=1003,
        msg="Failed to parse JSON from LLM response: Invalid JSON structure",
        data=None
    )
    
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg"
        }
    )
    
    assert response.status_code == 200  # API returns 200 with error in body
    
    data = response.json()
    assert data["code"] == 1003
    assert "Failed to parse JSON" in data["msg"]
    assert data["data"] is None


def test_parse_screenshot_missing_fields_error(client, mock_screenshot_parser_service):
    """Test error response when required fields are missing (error code 1004).
    
    Validates: Requirements 1.8, 7.4
    """
    # Configure mock to return error response
    mock_screenshot_parser_service.parse_screenshot.return_value = ParseScreenshotResponse(
        code=1004,
        msg="Missing or invalid required fields: Missing required field 'bubbles'",
        data=None
    )
    
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg"
        }
    )
    
    assert response.status_code == 200  # API returns 200 with error in body
    
    data = response.json()
    assert data["code"] == 1004
    assert "Missing or invalid required fields" in data["msg"]
    assert data["data"] is None


# ============================================================================
# Response Structure Tests
# ============================================================================


def test_parse_screenshot_response_structure(client, mock_screenshot_parser_service):
    """Test that response has correct structure.
    
    Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10
    """
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg"
        }
    )
    
    assert response.status_code == 200
    
    data = response.json()
    
    # Verify top-level structure
    assert "code" in data
    assert "msg" in data
    assert "data" in data
    
    # Verify data structure
    assert data["data"] is not None
    assert "image_meta" in data["data"]
    assert "participants" in data["data"]
    assert "bubbles" in data["data"]
    assert "layout" in data["data"]
    
    # Verify image_meta structure
    assert "width" in data["data"]["image_meta"]
    assert "height" in data["data"]["image_meta"]
    
    # Verify participants structure
    assert "self" in data["data"]["participants"]
    assert "other" in data["data"]["participants"]
    assert "id" in data["data"]["participants"]["self"]
    assert "nickname" in data["data"]["participants"]["self"]
    assert "id" in data["data"]["participants"]["other"]
    assert "nickname" in data["data"]["participants"]["other"]
    
    # Verify bubbles structure
    assert isinstance(data["data"]["bubbles"], list)
    if len(data["data"]["bubbles"]) > 0:
        bubble = data["data"]["bubbles"][0]
        assert "bubble_id" in bubble
        assert "bbox" in bubble
        assert "center_x" in bubble
        assert "center_y" in bubble
        assert "text" in bubble
        assert "sender" in bubble
        assert "column" in bubble
        assert "confidence" in bubble
        
        # Verify bbox structure
        assert "x1" in bubble["bbox"]
        assert "y1" in bubble["bbox"]
        assert "x2" in bubble["bbox"]
        assert "y2" in bubble["bbox"]
    
    # Verify layout structure
    assert "type" in data["data"]["layout"]
    assert "left_role" in data["data"]["layout"]
    assert "right_role" in data["data"]["layout"]


def test_parse_screenshot_error_response_structure(client, mock_screenshot_parser_service):
    """Test that error responses have correct structure.
    
    Validates: Requirements 9.1, 9.2
    """
    # Configure mock to return error response
    mock_screenshot_parser_service.parse_screenshot.return_value = ParseScreenshotResponse(
        code=1001,
        msg="Failed to download image",
        data=None
    )
    
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/invalid.jpg"
        }
    )
    
    assert response.status_code == 200
    
    data = response.json()
    
    # Verify error response structure
    assert "code" in data
    assert "msg" in data
    assert "data" in data
    
    assert data["code"] != 0
    assert isinstance(data["msg"], str)
    assert len(data["msg"]) > 0
    assert data["data"] is None


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_parse_screenshot_with_all_options(client, mock_screenshot_parser_service):
    """Test parsing with all possible options specified.
    
    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
    """
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg",
            "session_id": "full-options-test",
            "options": {
                "need_nickname": False,
                "need_sender": False,
                "force_two_columns": False,
                "app_type": "whatsapp"
            }
        }
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["code"] == 0
    
    # Verify all options were passed correctly
    call_args = mock_screenshot_parser_service.parse_screenshot.call_args[0][0]
    assert call_args.options.need_nickname is False
    assert call_args.options.need_sender is False
    assert call_args.options.force_two_columns is False
    assert call_args.options.app_type == "whatsapp"


def test_parse_screenshot_empty_bubbles_array(client, mock_screenshot_parser_service):
    """Test successful response with empty bubbles array.
    
    Validates: Requirements 9.6
    """
    # Configure mock to return response with no bubbles
    mock_screenshot_parser_service.parse_screenshot.return_value = ParseScreenshotResponse(
        code=0,
        msg="Success",
        data=ParsedScreenshotData(
            image_meta=ImageMeta(width=800, height=1200),
            participants=Participants(
                self=Participant(id="user1", nickname="User"),
                other=Participant(id="user2", nickname="Other")
            ),
            bubbles=[],  # Empty bubbles array
            layout=LayoutInfo(
                type="two_columns",
                left_role="talker",
                right_role="user"
            )
        )
    )
    
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/empty-screenshot.jpg"
        }
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["code"] == 0
    assert data["data"] is not None
    assert len(data["data"]["bubbles"]) == 0


def test_parse_screenshot_very_long_url(client, mock_screenshot_parser_service):
    """Test parsing with a very long URL.
    
    Validates: Requirements 6.1
    """
    long_url = "https://example.com/" + "a" * 2000 + ".jpg"
    
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": long_url
        }
    )
    
    assert response.status_code == 200
    
    # Verify the URL was passed correctly
    call_args = mock_screenshot_parser_service.parse_screenshot.call_args[0][0]
    assert call_args.image_url == long_url


def test_parse_screenshot_unicode_in_session_id(client, mock_screenshot_parser_service):
    """Test parsing with unicode characters in session_id.
    
    Validates: Requirements 6.1
    """
    response = client.post(
        "/api/v1/chat_screenshot/parse",
        json={
            "image_url": "https://example.com/screenshot.jpg",
            "session_id": "测试-session-🎉"
        }
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["code"] == 0
    
    # Verify unicode session_id was passed correctly
    call_args = mock_screenshot_parser_service.parse_screenshot.call_args[0][0]
    assert call_args.session_id == "测试-session-🎉"


# ============================================================================
# OpenAPI Documentation Tests
# ============================================================================


def test_openapi_schema_includes_endpoint(test_app):
    """Test that the endpoint is included in OpenAPI schema."""
    client = TestClient(test_app)
    response = client.get("/openapi.json")
    
    assert response.status_code == 200
    
    schema = response.json()
    assert "/api/v1/chat_screenshot/parse" in schema["paths"]
    
    endpoint = schema["paths"]["/api/v1/chat_screenshot/parse"]
    assert "post" in endpoint
    assert "summary" in endpoint["post"]
    assert "description" in endpoint["post"]


def test_openapi_schema_response_models(test_app):
    """Test that response models are documented in OpenAPI schema."""
    client = TestClient(test_app)
    response = client.get("/openapi.json")
    
    assert response.status_code == 200
    
    schema = response.json()
    endpoint = schema["paths"]["/api/v1/chat_screenshot/parse"]["post"]
    
    # Check that responses are documented
    assert "responses" in endpoint
    assert "200" in endpoint["responses"]
    assert "400" in endpoint["responses"]
    assert "500" in endpoint["responses"]
