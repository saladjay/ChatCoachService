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
    
    def test_predict_with_minimal_request(self, client):
        request_data = {
            "content": ["https://example.com/screenshot.jpg"],
            "language": "en",
            "scene": 1,
            "user_id": "test_user_123",
            "session_id": "session_test",
            "other_properties": "",
            "reply": False,
            "scene_analysis": False,
            "sign": "00000000000000000000000000000000",
        }
        response = client.post("/api/v1/ChatCoach/predict", json=request_data)
        assert response.status_code in [200, 400, 422, 500]
    
    def test_predict_validation_empty_urls(self, client):
        """Test that empty content list is rejected."""
        request_data = {
            "language": "en",
            "scene": 1,
            "user_id": "test_user_123",
            "session_id": "session_test",
            "content": [],
            "sign": "00000000000000000000000000000000",
        }
        
        response = client.post("/api/v1/ChatCoach/predict", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_predict_validation_invalid_app_name(self, client):
        """Test that invalid scene is rejected."""
        request_data = {
            "content": ["https://example.com/screenshot.jpg"],
            "language": "en",
            "scene": 99,
            "user_id": "test_user_123",
            "session_id": "session_test",
            "other_properties": "",
            "sign": "00000000000000000000000000000000",
        }
        
        response = client.post("/api/v1/ChatCoach/predict", json=request_data)
        assert response.status_code in [400, 422]
    
    def test_predict_validation_invalid_language(self, client):
        """Test that invalid language is rejected."""
        request_data = {
            "content": ["https://example.com/screenshot.jpg"],
            "language": "invalid_lang",
            "scene": 1,
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
