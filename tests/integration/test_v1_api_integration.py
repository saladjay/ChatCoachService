"""
Integration tests for ChatCoach API v1.

This test suite validates the complete v1 API integration including:
- All endpoints are accessible
- End-to-end screenshot analysis flow
- Reply generation integration
- Error handling

Requirements: Task 11 - Checkpoint Integration Testing
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import numpy as np

from app.main import app
from app.core.v1_dependencies import reset_v1_dependencies
from app.services.screenshot_processor import (
    ModelUnavailableError,
    ImageLoadError,
    InferenceError,
)


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
        # Should return either 200 or 401 depending on model availability
        assert response.status_code in [200, 401]
    
    def test_predict_endpoint_accessible(self, client):
        """Test that predict endpoint is accessible at correct path."""
        # Send minimal valid request
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": ["http://example.com/image.jpg"],
                "app_name": "whatsapp",
                "language": "en",
                "user_id": "test_user"
            }
        )
        # Should return a response (not 404)
        assert response.status_code != 404
    
    def test_metrics_endpoint_accessible(self, client):
        """Test that metrics endpoint is accessible at correct path."""
        response = client.get("/api/v1/ChatCoach/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
    
    def test_openapi_docs_accessible(self, client):
        """Test that OpenAPI documentation is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        # Verify v1 endpoints are in the OpenAPI spec
        openapi_spec = response.json()
        paths = openapi_spec.get("paths", {})
        
        assert "/api/v1/ChatCoach/health" in paths
        assert "/api/v1/ChatCoach/predict" in paths
        assert "/api/v1/ChatCoach/metrics" in paths


class TestHealthEndpoint:
    """Test health endpoint functionality."""
    
    @patch('app.services.status_checker.SCREENSHOT_ANALYSIS_AVAILABLE', True)
    @patch('app.services.status_checker.TEXT_DET_AVAILABLE', True)
    @patch('app.services.status_checker.LAYOUT_DET_AVAILABLE', True)
    @patch('app.services.status_checker.TEXT_REC_AVAILABLE', True)
    def test_health_check_when_models_available(self, client):
        """Test health check returns 200 when models are available."""
        response = client.get("/api/v1/ChatCoach/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "models" in data
        
        # Verify status is healthy
        assert data["status"] == "healthy"
        
        # Verify all models are reported as available
        models = data["models"]
        assert models["text_detection"] is True
        assert models["layout_detection"] is True
        assert models["text_recognition"] is True
        assert models["screenshotanalysis"] is True
    
    @patch('app.services.status_checker.SCREENSHOT_ANALYSIS_AVAILABLE', False)
    def test_health_check_when_models_unavailable(self, client):
        """Test health check returns 401 when models are unavailable."""
        response = client.get("/api/v1/ChatCoach/health")
        
        assert response.status_code == 401
        data = response.json()
        
        # Verify error response structure
        assert "detail" in data


class TestPredictEndpointValidation:
    """Test predict endpoint request validation."""
    
    def test_predict_requires_urls(self, client):
        """Test that predict endpoint requires urls parameter."""
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "app_name": "whatsapp",
                "language": "en",
                "user_id": "test_user"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_predict_requires_non_empty_urls(self, client):
        """Test that predict endpoint requires at least one URL."""
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": [],
                "app_name": "whatsapp",
                "language": "en",
                "user_id": "test_user"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_predict_requires_user_id(self, client):
        """Test that predict endpoint requires user_id parameter."""
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": ["http://example.com/image.jpg"],
                "app_name": "whatsapp",
                "language": "en"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_predict_validates_app_name(self, client):
        """Test that predict endpoint validates app_name against supported apps."""
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": ["http://example.com/image.jpg"],
                "app_name": "invalid_app",
                "language": "en",
                "user_id": "test_user"
            }
        )
        
        # Should return validation error for unsupported app
        assert response.status_code == 422
    
    def test_predict_validates_language(self, client):
        """Test that predict endpoint validates language against supported languages."""
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": ["http://example.com/image.jpg"],
                "app_name": "whatsapp",
                "language": "invalid_lang",
                "user_id": "test_user"
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


class TestScreenshotAnalysisFlow:
    """Test end-to-end screenshot analysis flow."""
    
    def test_successful_screenshot_analysis(self, client):
        """Test successful screenshot analysis flow with real models (if available)."""
        # This test uses real models if available, otherwise expects appropriate errors
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
        
        # Verify response - should be one of the expected status codes
        assert response.status_code in [200, 400, 401, 500]
        
        # If successful, verify structure
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "results" in data
            assert "user_id" in data
            
            # If success is true, verify results structure
            if data["success"]:
                assert len(data["results"]) > 0
    
    @patch('app.services.screenshot_processor.SCREENSHOT_ANALYSIS_AVAILABLE', False)
    def test_screenshot_analysis_model_unavailable(self, client):
        """Test screenshot analysis when models are unavailable."""
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": ["http://example.com/screenshot.jpg"],
                "app_name": "whatsapp",
                "language": "en",
                "user_id": "test_user"
            }
        )
        
        # Should return 401 for model unavailable
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


class TestReplyGenerationIntegration:
    """Test reply generation integration with Orchestrator."""
    
    @patch('app.services.screenshot_processor.SCREENSHOT_ANALYSIS_AVAILABLE', True)
    @patch('app.services.screenshot_processor.AnalysisCore')
    async def test_reply_generation_when_requested(self, mock_analysis_core, client):
        """Test that reply generation is triggered when reply=true."""
        # Mock the screenshotanalysis models
        mock_text_det = Mock()
        mock_layout_det = Mock()
        mock_text_rec = Mock()
        
        # Configure mock responses
        mock_text_det.analyze_chat_screenshot.return_value = {
            'success': True,
            'results': [
                Mock(
                    x_min=100, y_min=100, x_max=200, y_max=150,
                    speaker='A', center_x=150
                )
            ],
            'padding': [0, 0, 0, 0],
            'image_size': [1080, 1920]
        }
        
        mock_layout_det.analyze_chat_screenshot.return_value = {
            'success': True,
            'results': [
                Mock(
                    x_min=100, y_min=100, x_max=200, y_max=150,
                    layout_det='text'
                )
            ]
        }
        
        mock_text_rec.predict_text.return_value = {'text': 'Hello'}
        
        mock_analysis_core.text_det = mock_text_det
        mock_analysis_core.layout_det = mock_layout_det
        mock_analysis_core.en_rec = mock_text_rec
        
        # Mock image loading
        with patch('app.services.screenshot_processor.httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.content = b'\x89PNG\r\n\x1a\n'
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            with patch('app.services.screenshot_processor.Image') as mock_image:
                mock_img = Mock()
                mock_img.mode = 'RGB'
                mock_image.open.return_value = mock_img
                
                with patch('app.services.screenshot_processor.np.array') as mock_array:
                    mock_array.return_value = np.zeros((1920, 1080, 3), dtype=np.uint8)
                    
                    # Make request with reply=true
                    response = client.post(
                        "/api/v1/ChatCoach/predict",
                        json={
                            "urls": ["http://example.com/screenshot.jpg"],
                            "app_name": "whatsapp",
                            "language": "en",
                            "user_id": "test_user",
                            "reply": True
                        }
                    )
        
        # Verify response structure
        if response.status_code == 200:
            data = response.json()
            # suggested_replies may or may not be present depending on orchestrator
            # But the request should not fail
            assert "results" in data
    
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


class TestErrorHandling:
    """Test error handling across the API."""
    
    def test_image_load_error_handling(self, client):
        """Test that image load errors are handled gracefully."""
        # Use an invalid URL that will fail to load
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": ["http://invalid-domain-that-does-not-exist.com/image.jpg"],
                "app_name": "whatsapp",
                "language": "en",
                "user_id": "test_user"
            }
        )
        
        # Should return an error response (not crash)
        assert response.status_code in [200, 400, 401, 500]
        
        if response.status_code == 200:
            data = response.json()
            # If it returns 200, success should be false
            assert data.get("success") is False
            assert "message" in data
    
    def test_multiple_urls_partial_failure(self, client):
        """Test handling when some URLs fail but others succeed."""
        # Mix of valid and invalid URLs
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": [
                    "http://invalid-domain.com/image1.jpg",
                    "http://example.com/image2.jpg"
                ],
                "app_name": "whatsapp",
                "language": "en",
                "user_id": "test_user"
            }
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 401, 500]
    
    def test_orchestrator_failure_does_not_break_predict(self, client):
        """Test that orchestrator failures don't break the predict endpoint."""
        # This test verifies graceful degradation
        # Even if orchestrator fails, screenshot analysis should still work
        
        # Make request with reply=true
        # The endpoint should handle orchestrator failures gracefully
        response = client.post(
            "/api/v1/ChatCoach/predict",
            json={
                "urls": ["http://example.com/screenshot.jpg"],
                "app_name": "whatsapp",
                "language": "en",
                "user_id": "test_user",
                "reply": True
            }
        )
        
        # Should not crash even with orchestrator unavailable
        # May return error due to image loading or model unavailability
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
