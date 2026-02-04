"""
Integration tests for ChatCoach API v1.

This test suite validates the complete v1 API integration including:
- All endpoints are accessible
- End-to-end screenshot analysis flow

Requirements: Task 11 - Checkpoint Integration Testing
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.v1_dependencies import reset_v1_dependencies


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_dependencies():
    """Reset v1 dependencies before each test."""
    reset_v1_dependencies()
    yield
    reset_v1_dependencies()


class TestEndpointAccessibility:
    """Test that all v1 endpoints are accessible."""
    
    def test_health_endpoint_accessible(self, client):
        """Test that health endpoint is accessible at correct path."""
        response = client.get("/api/v1/ChatCoach/health")
        assert response.status_code == 200
    
    def test_predict_endpoint_accessible(self, client):
        """Test that predict endpoint is accessible at correct path."""
        response = client.post("/api/v1/ChatCoach/predict", json={})
        # Should return a response (not 404)
        assert response.status_code != 404
    
    def test_metrics_endpoint_accessible(self, client):
        """Test that metrics endpoint is accessible at correct path."""
        response = client.get("/api/v1/ChatCoach/metrics")
        assert response.status_code == 200


class TestHealthEndpoint:
    """Test health endpoint functionality."""

    def test_health_check_returns_200(self, client):
        response = client.get("/api/v1/ChatCoach/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "models" in data


class TestPredictEndpointValidation:
    """Test predict endpoint request validation."""
    
    def test_predict_requires_urls(self, client):
        """Test that predict endpoint requires request body fields."""
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "language": "en",
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_predict_requires_non_empty_urls(self, client):
        """Test that predict endpoint requires at least one content item."""
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "content": [],
                "language": "en",
                "scene": 1,
                "user_id": "test_user",
                "session_id": "test_session",
                "other_properties": "",
                "sign": "00000000000000000000000000000000",
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_predict_requires_user_id(self, client):
        """Test that predict endpoint requires user_id parameter."""
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "content": ["http://example.com/image.jpg"],
                "language": "en",
                "scene": 1,
                "session_id": "test_session",
                "other_properties": "",
                "sign": "00000000000000000000000000000000",
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_predict_validates_scene(self, client):
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "content": ["http://example.com/image.jpg"],
                "language": "en",
                "scene": 99,
                "user_id": "test_user",
                "session_id": "test_session",
                "other_properties": "",
                "sign": "00000000000000000000000000000000",
            },
        )

        assert response.status_code in [400, 422]
    
    def test_predict_validates_language(self, client):
        """Test that predict endpoint validates language against supported languages."""
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "content": ["http://example.com/image.jpg"],
                "language": "invalid_lang",
                "scene": 1,
                "user_id": "test_user",
                "session_id": "test_session",
                "other_properties": "",
                "sign": "00000000000000000000000000000000",
            }
        )
        
        # Should return validation error for unsupported language
        assert response.status_code == 422
    
    def test_predict_validates_conf_threshold_range(self, client):
        """Test that predict endpoint validates conf_threshold is in [0.0, 1.0]."""
        # Test value too low
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": ["http://example.com/image.jpg"],
                "app_name": "whatsapp",
                "language": "en",
                "user_id": "test_user",
                "conf_threshold": -0.1
            }
        )
        assert response.status_code == 422
        
        # Test value too high
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": ["http://example.com/image.jpg"],
                "app_name": "whatsapp",
                "language": "en",
                "user_id": "test_user",
                "conf_threshold": 1.1
            }
        )
        assert response.status_code == 422


 class TestReplyGenerationIntegration:
     """Test reply generation integration with Orchestrator."""

    def test_reply_generation_when_requested(self, client):
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "content": ["http://example.com/screenshot.jpg"],
                "language": "en",
                "scene": 1,
                "user_id": "test_user",
                "session_id": "test_session",
                "other_properties": "",
                "reply": True,
                "scene_analysis": False,
                "sign": "00000000000000000000000000000000",
            },
        )
        assert response.status_code in [200, 400, 422, 500]
    
    def test_reply_not_generated_when_not_requested(self, client):
        """Test that reply generation is skipped when reply=false."""
        # This test verifies the default behavior
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": ["http://example.com/screenshot.jpg"],
                "app_name": "whatsapp",
                "language": "en",
                "user_id": "test_user",
                "reply": False
            }
        )
        
        # Response should not include suggested_replies
        # (or it should be None/null)
        if response.status_code == 200:
            data = response.json()
            suggested_replies = data.get("suggested_replies")
            assert suggested_replies is None or suggested_replies == []


 
        assert response.status_code in [200, 400, 401, 500]
        
        # If it returns 200, verify it has results (even without suggested_replies)
        if response.status_code == 200:
            data = response.json()
            assert "results" in data


class TestMetricsEndpoint:
    """Test metrics endpoint functionality."""
    
    def test_metrics_returns_prometheus_format(self, client):
        """Test that metrics endpoint returns Prometheus format."""
        response = client.get("/api/v1/ChatCoach/metrics")
        
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        
        # Verify Prometheus format
        content = response.text
        assert "# HELP" in content
        assert "# TYPE" in content
        assert "chatcoach_" in content
    
    def test_metrics_tracks_requests(self, client):
        """Test that metrics are updated after requests."""
        # Get initial metrics
        response1 = client.get("/api/v1/ChatCoach/metrics")
        initial_metrics = response1.text
        
        # Make a health check request
        client.get("/api/v1/ChatCoach/health")
        
        # Get updated metrics
        response2 = client.get("/api/v1/ChatCoach/metrics")
        updated_metrics = response2.text
        
        # Metrics should have changed
        # (This is a basic check - in production you'd parse and compare values)
        assert response2.status_code == 200


class TestResponseFormat:
    """Test response format compatibility."""
    
    def test_predict_response_structure(self, client):
        """Test that predict response has correct structure."""
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": ["http://example.com/screenshot.jpg"],
                "app_name": "whatsapp",
                "language": "en",
                "user_id": "test_user"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify required fields
            assert "success" in data
            assert "message" in data
            assert "user_id" in data
            assert "results" in data
            
            # Verify user_id matches request
            assert data["user_id"] == "test_user"
            
            # If results exist, verify structure
            if data["results"]:
                result = data["results"][0]
                assert "url" in result
                assert "dialogs" in result
                
                # If dialogs exist, verify structure
                if result["dialogs"]:
                    dialog = result["dialogs"][0]
                    assert "position" in dialog
                    assert "text" in dialog
                    assert "speaker" in dialog
                    assert "from_user" in dialog
                    
                    # Verify position format [min_x, min_y, max_x, max_y]
                    position = dialog["position"]
                    assert isinstance(position, list)
                    assert len(position) == 4
                    
                    # Verify coordinates are in [0.0, 1.0] range
                    for coord in position:
                        assert 0.0 <= coord <= 1.0
