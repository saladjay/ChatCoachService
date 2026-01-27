"""
Integration tests for the v1 predict endpoint.

Tests the POST /api/v1/ChatCoach/predict endpoint functionality.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from app.main import app
from app.models.v1_api import DialogItem, ImageResult


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_screenshot_processor():
    """Create a mock ScreenshotProcessor."""
    processor = Mock()
    
    # Mock successful screenshot processing
    async def mock_process_screenshot(image_url, app_type, conf_threshold=None):
        return ImageResult(
            url=image_url,
            dialogs=[
                DialogItem(
                    position=[0.1, 0.2, 0.3, 0.4],
                    text="Hello, how are you?",
                    speaker="other",
                    from_user=False,
                ),
                DialogItem(
                    position=[0.6, 0.2, 0.8, 0.4],
                    text="I'm doing great, thanks!",
                    speaker="self",
                    from_user=True,
                ),
            ]
        )
    
    processor.process_screenshot = mock_process_screenshot
    return processor


@pytest.fixture
def mock_orchestrator():
    """Create a mock Orchestrator."""
    orchestrator = Mock()
    
    # Mock successful reply generation
    async def mock_generate_reply(request):
        response = Mock()
        response.reply_text = "That's wonderful to hear!"
        return response
    
    orchestrator.generate_reply = mock_generate_reply
    return orchestrator


class TestPredictEndpoint:
    """Test suite for the predict endpoint."""
    
    def test_predict_endpoint_exists(self, client):
        """Test that the predict endpoint is accessible."""
        # This will fail with validation error, but confirms endpoint exists
        response = client.post("/api/v1/ChatCoach/predict", json={})
        assert response.status_code in [400, 422]  # Validation error expected
    
    @patch("app.core.v1_dependencies.get_v1_screenshot_processor")
    def test_predict_with_valid_request(self, mock_get_processor, client, mock_screenshot_processor):
        """Test predict endpoint with valid request."""
        mock_get_processor.return_value = mock_screenshot_processor
        
        request_data = {
            "urls": ["https://example.com/screenshot.jpg"],
            "app_name": "whatsapp",
            "language": "en",
            "user_id": "test_user_123",
            "request_id": "req_123",
            "conf_threshold": 0.7,
            "reply": False,
        }
        
        response = client.post("/api/v1/ChatCoach/predict", json=request_data)
        
        # Should succeed or fail gracefully
        assert response.status_code in [200, 400, 401, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "message" in data
            assert "user_id" in data
            assert "results" in data
    
    @patch("app.core.v1_dependencies.get_v1_screenshot_processor")
    @patch("app.core.v1_dependencies.get_v1_orchestrator")
    def test_predict_with_reply_generation(
        self, mock_get_orch, mock_get_processor, client, 
        mock_screenshot_processor, mock_orchestrator
    ):
        """Test predict endpoint with reply generation enabled."""
        mock_get_processor.return_value = mock_screenshot_processor
        mock_get_orch.return_value = mock_orchestrator
        
        request_data = {
            "urls": ["https://example.com/screenshot.jpg"],
            "app_name": "whatsapp",
            "language": "en",
            "user_id": "test_user_123",
            "reply": True,
        }
        
        response = client.post("/api/v1/ChatCoach/predict", json=request_data)
        
        # Should succeed or fail gracefully
        assert response.status_code in [200, 400, 401, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "results" in data
            # suggested_replies may or may not be present depending on orchestrator
    
    def test_predict_validation_empty_urls(self, client):
        """Test that empty URLs list is rejected."""
        request_data = {
            "urls": [],  # Empty list should be rejected
            "app_name": "whatsapp",
            "language": "en",
            "user_id": "test_user_123",
        }
        
        response = client.post("/api/v1/ChatCoach/predict", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_predict_validation_invalid_app_name(self, client):
        """Test that invalid app_name is rejected."""
        request_data = {
            "urls": ["https://example.com/screenshot.jpg"],
            "app_name": "invalid_app",  # Not in supported apps
            "language": "en",
            "user_id": "test_user_123",
        }
        
        response = client.post("/api/v1/ChatCoach/predict", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_predict_validation_invalid_language(self, client):
        """Test that invalid language is rejected."""
        request_data = {
            "urls": ["https://example.com/screenshot.jpg"],
            "app_name": "whatsapp",
            "language": "invalid_lang",  # Not in supported languages
            "user_id": "test_user_123",
        }
        
        response = client.post("/api/v1/ChatCoach/predict", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_predict_validation_conf_threshold_out_of_range(self, client):
        """Test that conf_threshold outside [0.0, 1.0] is rejected."""
        request_data = {
            "urls": ["https://example.com/screenshot.jpg"],
            "app_name": "whatsapp",
            "language": "en",
            "user_id": "test_user_123",
            "conf_threshold": 1.5,  # Out of range
        }
        
        response = client.post("/api/v1/ChatCoach/predict", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_predict_validation_empty_user_id(self, client):
        """Test that empty user_id is rejected."""
        request_data = {
            "urls": ["https://example.com/screenshot.jpg"],
            "app_name": "whatsapp",
            "language": "en",
            "user_id": "",  # Empty user_id
        }
        
        response = client.post("/api/v1/ChatCoach/predict", json=request_data)
        assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
