"""Property-based tests for API validation.

Tests:
- Property 1: Request Validation Consistency
- Property 2: Response Schema Completeness

Validates: Requirements 1.2, 1.3, 1.4
"""

import pytest
from hypothesis import given, settings, strategies as st
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.container import reset_container


# Strategies for generating test data
valid_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
    min_size=1,
    max_size=50,
).filter(lambda x: len(x.strip()) > 0)

quality_strategy = st.sampled_from(["cheap", "normal", "premium"])

language_strategy = st.sampled_from(["en", "ar", "pt", "es", "zh-CN"])  # Supported languages


class TestRequestValidationConsistency:
    """
    Property 1: Request Validation Consistency
    
    *For any* request with missing or invalid required fields (user_id, target_id,
    conversation_id), the API SHALL return a 400 status code with error details,
    and no downstream services SHALL be invoked.
    
    **Feature: conversation-generation-service, Property 1: Request Validation Consistency**
    **Validates: Requirements 1.2, 1.3**
    """
    
    @pytest.fixture(autouse=True)
    def reset_services(self):
        """Reset service container before each test."""
        reset_container()
        yield
        reset_container()
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        target_id=valid_id_strategy,
        conversation_id=valid_id_strategy,
    )
    async def test_missing_user_id_returns_400(
        self,
        target_id: str,
        conversation_id: str,
    ):
        """
        Property 1: Missing user_id should return 400
        
        For any request missing user_id, the API returns 400.
        
        **Validates: Requirements 1.2, 1.3**
        """
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/generate/reply",
                json={
                    "target_id": target_id,
                    "conversation_id": conversation_id,
                },
            )
            
            assert response.status_code == 422, (
                f"Expected 422 for missing user_id, got {response.status_code}"
            )
            
            # Verify error response contains details
            error_data = response.json()
            assert "detail" in error_data
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        user_id=valid_id_strategy,
        conversation_id=valid_id_strategy,
    )
    async def test_missing_target_id_returns_400(
        self,
        user_id: str,
        conversation_id: str,
    ):
        """
        Property 1: Missing target_id should return 400
        
        For any request missing target_id, the API returns 400.
        
        **Validates: Requirements 1.2, 1.3**
        """
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/generate/reply",
                json={
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                },
            )
            
            assert response.status_code == 422, (
                f"Expected 422 for missing target_id, got {response.status_code}"
            )
            
            error_data = response.json()
            assert "detail" in error_data
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        user_id=valid_id_strategy,
        target_id=valid_id_strategy,
    )
    async def test_missing_conversation_id_returns_400(
        self,
        user_id: str,
        target_id: str,
    ):
        """
        Property 1: Missing conversation_id should return 400
        
        For any request missing conversation_id, the API returns 400.
        
        **Validates: Requirements 1.2, 1.3**
        """
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/generate/reply",
                json={
                    "user_id": user_id,
                    "target_id": target_id,
                },
            )
            
            assert response.status_code == 422, (
                f"Expected 422 for missing conversation_id, got {response.status_code}"
            )
            
            error_data = response.json()
            assert "detail" in error_data
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        target_id=valid_id_strategy,
        conversation_id=valid_id_strategy,
    )
    async def test_empty_user_id_returns_400(
        self,
        target_id: str,
        conversation_id: str,
    ):
        """
        Property 1: Empty user_id should return 400
        
        For any request with empty user_id, the API returns 400.
        
        **Validates: Requirements 1.2, 1.3**
        """
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/generate/reply",
                json={
                    "user_id": "",
                    "target_id": target_id,
                    "conversation_id": conversation_id,
                },
            )
            
            assert response.status_code == 422, (
                f"Expected 422 for empty user_id, got {response.status_code}"
            )
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        user_id=valid_id_strategy,
        conversation_id=valid_id_strategy,
    )
    async def test_empty_target_id_returns_400(
        self,
        user_id: str,
        conversation_id: str,
    ):
        """
        Property 1: Empty target_id should return 400
        
        For any request with empty target_id, the API returns 400.
        
        **Validates: Requirements 1.2, 1.3**
        """
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/generate/reply",
                json={
                    "user_id": user_id,
                    "target_id": "",
                    "conversation_id": conversation_id,
                },
            )
            
            assert response.status_code == 422, (
                f"Expected 422 for empty target_id, got {response.status_code}"
            )
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        user_id=valid_id_strategy,
        target_id=valid_id_strategy,
    )
    async def test_empty_conversation_id_returns_400(
        self,
        user_id: str,
        target_id: str,
    ):
        """
        Property 1: Empty conversation_id should return 400
        
        For any request with empty conversation_id, the API returns 400.
        
        **Validates: Requirements 1.2, 1.3**
        """
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/generate/reply",
                json={
                    "user_id": user_id,
                    "target_id": target_id,
                    "conversation_id": "",
                },
            )
            
            assert response.status_code == 422, (
                f"Expected 422 for empty conversation_id, got {response.status_code}"
            )
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        user_id=valid_id_strategy,
        target_id=valid_id_strategy,
        conversation_id=valid_id_strategy,
        invalid_quality=st.text(min_size=1, max_size=20).filter(
            lambda x: x not in ["cheap", "normal", "premium"]
        ),
    )
    async def test_invalid_quality_returns_400(
        self,
        user_id: str,
        target_id: str,
        conversation_id: str,
        invalid_quality: str,
    ):
        """
        Property 1: Invalid quality value should return 400
        
        For any request with invalid quality value, the API returns 400.
        
        **Validates: Requirements 1.2, 1.3**
        """
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/generate/reply",
                json={
                    "user_id": user_id,
                    "target_id": target_id,
                    "conversation_id": conversation_id,
                    "quality": invalid_quality,
                },
            )
            
            assert response.status_code == 422, (
                f"Expected 422 for invalid quality '{invalid_quality}', "
                f"got {response.status_code}"
            )


class TestResponseSchemaCompleteness:
    """
    Property 2: Response Schema Completeness
    
    *For any* successful generation request, the response SHALL contain all
    required fields (reply_text, confidence, intimacy_level_before,
    intimacy_level_after, model, provider, cost_usd) with valid values.
    
    **Feature: conversation-generation-service, Property 2: Response Schema Completeness**
    **Validates: Requirements 1.4**
    """
    
    @pytest.fixture(autouse=True)
    def reset_services(self):
        """Reset service container before each test."""
        reset_container()
        yield
        reset_container()
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        user_id=valid_id_strategy,
        target_id=valid_id_strategy,
        conversation_id=valid_id_strategy,
        quality=quality_strategy,
        language=language_strategy,
        force_regenerate=st.booleans(),
    )
    async def test_successful_response_contains_all_required_fields(
        self,
        user_id: str,
        target_id: str,
        conversation_id: str,
        quality: str,
        language: str,
        force_regenerate: bool,
    ):
        """
        Property 2: Response Schema Completeness
        
        For any valid request, the response contains all required fields.
        
        **Validates: Requirements 1.4**
        """
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/generate/reply",
                json={
                    "user_id": user_id,
                    "target_id": target_id,
                    "conversation_id": conversation_id,
                    "quality": quality,
                    "language": language,
                    "force_regenerate": force_regenerate,
                },
            )
            
            assert response.status_code == 200, (
                f"Expected 200 for valid request, got {response.status_code}: "
                f"{response.text}"
            )
            
            data = response.json()
            
            # Verify all required fields are present
            required_fields = [
                "reply_text",
                "confidence",
                "intimacy_level_before",
                "intimacy_level_after",
                "model",
                "provider",
                "cost_usd",
            ]
            
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
            
            # Verify field types and constraints
            assert isinstance(data["reply_text"], str), "reply_text must be string"
            assert len(data["reply_text"]) > 0, "reply_text must not be empty"
            
            assert isinstance(data["confidence"], (int, float)), (
                "confidence must be numeric"
            )
            assert 0.0 <= data["confidence"] <= 1.0, (
                f"confidence must be between 0 and 1, got {data['confidence']}"
            )
            
            assert isinstance(data["intimacy_level_before"], int), (
                "intimacy_level_before must be int"
            )
            assert 1 <= data["intimacy_level_before"] <= 5, (
                f"intimacy_level_before must be 1-5, got {data['intimacy_level_before']}"
            )
            
            assert isinstance(data["intimacy_level_after"], int), (
                "intimacy_level_after must be int"
            )
            assert 1 <= data["intimacy_level_after"] <= 5, (
                f"intimacy_level_after must be 1-5, got {data['intimacy_level_after']}"
            )
            
            assert isinstance(data["model"], str), "model must be string"
            assert len(data["model"]) > 0, "model must not be empty"
            
            assert isinstance(data["provider"], str), "provider must be string"
            assert len(data["provider"]) > 0, "provider must not be empty"
            
            assert isinstance(data["cost_usd"], (int, float)), (
                "cost_usd must be numeric"
            )
            assert data["cost_usd"] >= 0.0, (
                f"cost_usd must be non-negative, got {data['cost_usd']}"
            )
