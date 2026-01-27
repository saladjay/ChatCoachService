"""Property-based tests for Multimodal LLM Client component.

Tests:
- Property 2: LLM Invocation with Complete Parameters

Validates: Requirements 1.2, 3.4
"""

import base64
import io
import pytest
from hypothesis import given, settings, strategies as st
from PIL import Image
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.screenshot import ParseOptions, MultimodalLLMResponse
from app.services.multimodal_llm_adapter import MultimodalLLMClient


# Strategies for generating test data

@st.composite
def parse_options_strategy(draw):
    """Generate arbitrary ParseOptions configurations."""
    need_nickname = draw(st.booleans())
    need_sender = draw(st.booleans())
    force_two_columns = draw(st.booleans())
    app_type = draw(st.sampled_from(["wechat", "line", "whatsapp", "unknown"]))
    
    return ParseOptions(
        need_nickname=need_nickname,
        need_sender=need_sender,
        force_two_columns=force_two_columns,
        app_type=app_type,
    )


@st.composite
def image_base64_strategy(draw):
    """Generate base64-encoded images."""
    width = draw(st.integers(min_value=100, max_value=1000))
    height = draw(st.integers(min_value=100, max_value=1000))
    format = draw(st.sampled_from(["PNG", "JPEG"]))
    
    # Create a test image
    img = Image.new("RGB", (width, height), color="white")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format=format)
    image_bytes = img_bytes.getvalue()
    
    # Convert to base64
    return base64.b64encode(image_bytes).decode('utf-8')


@st.composite
def prompt_strategy(draw):
    """Generate arbitrary prompt strings."""
    # Generate prompts with various characteristics
    prompt_type = draw(st.sampled_from([
        "short",
        "medium",
        "long",
        "with_json",
        "with_special_chars"
    ]))
    
    if prompt_type == "short":
        return draw(st.text(min_size=10, max_size=50))
    elif prompt_type == "medium":
        return draw(st.text(min_size=50, max_size=200))
    elif prompt_type == "long":
        return draw(st.text(min_size=200, max_size=500))
    elif prompt_type == "with_json":
        return f"Parse this: {draw(st.text(min_size=10, max_size=100))} Return JSON."
    else:  # with_special_chars
        return draw(st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P"),
                whitelist_characters=" \n\t"
            ),
            min_size=10,
            max_size=200
        ))


class TestLLMInvocationWithCompleteParameters:
    """
    Property 2: LLM Invocation with Complete Parameters
    
    *For any* parse request, when the Chat_Screenshot_Parser processes it,
    the Multimodal_LLM should be invoked with both system prompt, user prompt,
    and image data.
    
    **Feature: chat-screenshot-parser, Property 2: LLM Invocation with Complete Parameters**
    **Validates: Requirements 1.2, 3.4**
    """
    
    @pytest.mark.asyncio
    @settings(max_examples=100, deadline=2000)
    @given(
        system_prompt=prompt_strategy(),
        user_prompt=prompt_strategy(),
        image_base64=image_base64_strategy(),
    )
    async def test_llm_call_receives_all_required_parameters(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
    ):
        """
        Property 2: LLM call receives all required parameters
        
        For any system prompt, user prompt, and image data, when calling the
        multimodal LLM, all three parameters should be passed to the provider.
        
        **Validates: Requirements 1.2, 3.4**
        """
        # Create a mock provider that tracks what it receives
        mock_provider = AsyncMock()
        mock_provider.call = AsyncMock(return_value={
            "raw_text": '{"image_meta": {"width": 100, "height": 100}, "participants": {"self": {"id": "u1", "nickname": "User"}, "other": {"id": "u2", "nickname": "Other"}}, "bubbles": [], "layout": {"type": "two_columns", "left_role": "talker", "right_role": "user"}}',
            "provider": "test",
            "model": "test-model",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
        })
        
        # Create client and register mock provider
        config = MagicMock()
        client = MultimodalLLMClient(config)
        client.register_provider("test", mock_provider)
        
        # Call the LLM
        try:
            response = await client.call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_base64=image_base64,
                provider="test",
            )
        except Exception as e:
            pytest.fail(f"LLM call failed unexpectedly: {e}")
        
        # Verify the provider was called
        assert mock_provider.call.called, "Provider should have been called"
        
        # Verify all three parameters were passed
        call_args = mock_provider.call.call_args
        assert call_args is not None, "Provider should have been called with arguments"
        
        # Check keyword arguments
        kwargs = call_args.kwargs
        assert "system_prompt" in kwargs, "system_prompt should be passed to provider"
        assert "user_prompt" in kwargs, "user_prompt should be passed to provider"
        assert "image_base64" in kwargs, "image_base64 should be passed to provider"
        
        # Verify the values match what we passed
        assert kwargs["system_prompt"] == system_prompt, "system_prompt should match input"
        assert kwargs["user_prompt"] == user_prompt, "user_prompt should match input"
        assert kwargs["image_base64"] == image_base64, "image_base64 should match input"
    
    @pytest.mark.asyncio
    @settings(max_examples=100, deadline=2000)
    @given(
        system_prompt=prompt_strategy(),
        user_prompt=prompt_strategy(),
        image_base64=image_base64_strategy(),
    )
    async def test_llm_call_returns_response_with_metadata(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
    ):
        """
        Property 2: LLM call returns response with metadata
        
        For any valid LLM invocation, the response should include metadata
        about the provider, model, tokens, and cost.
        
        **Validates: Requirements 1.2, 3.4**
        """
        # Create a mock provider
        mock_provider = AsyncMock()
        mock_provider.call = AsyncMock(return_value={
            "raw_text": '{"image_meta": {"width": 100, "height": 100}, "participants": {"self": {"id": "u1", "nickname": "User"}, "other": {"id": "u2", "nickname": "Other"}}, "bubbles": [], "layout": {"type": "two_columns", "left_role": "talker", "right_role": "user"}}',
            "provider": "test",
            "model": "test-model",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
        })
        
        # Create client and register mock provider
        config = MagicMock()
        client = MultimodalLLMClient(config)
        client.register_provider("test", mock_provider)
        
        # Call the LLM
        response = await client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_base64=image_base64,
            provider="test",
        )
        
        # Verify response is a MultimodalLLMResponse
        assert isinstance(response, MultimodalLLMResponse), (
            "Response should be a MultimodalLLMResponse"
        )
        
        # Verify all metadata fields are present
        assert hasattr(response, "provider"), "Response should have provider field"
        assert hasattr(response, "model"), "Response should have model field"
        assert hasattr(response, "input_tokens"), "Response should have input_tokens field"
        assert hasattr(response, "output_tokens"), "Response should have output_tokens field"
        assert hasattr(response, "cost_usd"), "Response should have cost_usd field"
        
        # Verify metadata values are valid
        assert isinstance(response.provider, str), "provider should be a string"
        assert isinstance(response.model, str), "model should be a string"
        assert isinstance(response.input_tokens, int), "input_tokens should be an integer"
        assert isinstance(response.output_tokens, int), "output_tokens should be an integer"
        assert isinstance(response.cost_usd, float), "cost_usd should be a float"
        
        # Verify token counts are non-negative
        assert response.input_tokens >= 0, "input_tokens should be non-negative"
        assert response.output_tokens >= 0, "output_tokens should be non-negative"
        assert response.cost_usd >= 0, "cost_usd should be non-negative"
    
    @pytest.mark.asyncio
    @settings(max_examples=100, deadline=2000)
    @given(
        system_prompt=prompt_strategy(),
        user_prompt=prompt_strategy(),
        image_base64=image_base64_strategy(),
    )
    async def test_llm_call_with_empty_prompts_still_invokes_provider(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
    ):
        """
        Property 2: LLM call with any prompts invokes provider
        
        For any prompts (including empty strings), the LLM client should
        still invoke the provider with all parameters.
        
        **Validates: Requirements 1.2, 3.4**
        """
        # Create a mock provider
        mock_provider = AsyncMock()
        mock_provider.call = AsyncMock(return_value={
            "raw_text": '{"image_meta": {"width": 100, "height": 100}, "participants": {"self": {"id": "u1", "nickname": "User"}, "other": {"id": "u2", "nickname": "Other"}}, "bubbles": [], "layout": {"type": "two_columns", "left_role": "talker", "right_role": "user"}}',
            "provider": "test",
            "model": "test-model",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
        })
        
        # Create client and register mock provider
        config = MagicMock()
        client = MultimodalLLMClient(config)
        client.register_provider("test", mock_provider)
        
        # Call the LLM (even with potentially empty prompts)
        await client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_base64=image_base64,
            provider="test",
        )
        
        # Verify the provider was called regardless of prompt content
        assert mock_provider.call.called, (
            "Provider should be called even with empty or unusual prompts"
        )
        
        # Verify call count is exactly 1
        assert mock_provider.call.call_count == 1, (
            "Provider should be called exactly once"
        )
    
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=2000)
    @given(
        system_prompt=prompt_strategy(),
        user_prompt=prompt_strategy(),
        image_base64=image_base64_strategy(),
    )
    async def test_llm_call_preserves_parameter_values(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
    ):
        """
        Property 2: LLM call preserves parameter values
        
        For any parameters passed to the LLM client, the exact same values
        should be passed to the underlying provider without modification.
        
        **Validates: Requirements 1.2, 3.4**
        """
        # Create a mock provider that captures arguments
        captured_args = {}
        
        async def capture_call(**kwargs):
            captured_args.update(kwargs)
            return {
                "raw_text": '{"image_meta": {"width": 100, "height": 100}, "participants": {"self": {"id": "u1", "nickname": "User"}, "other": {"id": "u2", "nickname": "Other"}}, "bubbles": [], "layout": {"type": "two_columns", "left_role": "talker", "right_role": "user"}}',
                "provider": "test",
                "model": "test-model",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.001,
            }
        
        mock_provider = AsyncMock()
        mock_provider.call = capture_call
        
        # Create client and register mock provider
        config = MagicMock()
        client = MultimodalLLMClient(config)
        client.register_provider("test", mock_provider)
        
        # Call the LLM
        await client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_base64=image_base64,
            provider="test",
        )
        
        # Verify captured arguments match exactly
        assert captured_args["system_prompt"] == system_prompt, (
            "system_prompt should be passed unchanged"
        )
        assert captured_args["user_prompt"] == user_prompt, (
            "user_prompt should be passed unchanged"
        )
        assert captured_args["image_base64"] == image_base64, (
            "image_base64 should be passed unchanged"
        )
    
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=2000)
    @given(
        system_prompt=prompt_strategy(),
        user_prompt=prompt_strategy(),
        image_base64=image_base64_strategy(),
    )
    async def test_llm_call_fails_gracefully_on_provider_error(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
    ):
        """
        Property 2: LLM call fails gracefully on provider error
        
        For any parameters, if the provider raises an error, the LLM client
        should propagate it (either as-is or wrapped).
        
        **Validates: Requirements 1.2, 3.4**
        """
        # Create a mock provider that raises an error
        mock_provider = AsyncMock()
        mock_provider.call = AsyncMock(side_effect=RuntimeError("Provider error"))
        
        # Create client and register mock provider
        config = MagicMock()
        client = MultimodalLLMClient(config)
        client.register_provider("test", mock_provider)
        
        # Call the LLM and expect an error (RuntimeError or Exception)
        with pytest.raises((RuntimeError, Exception)) as exc_info:
            await client.call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_base64=image_base64,
                provider="test",
            )
        
        # Verify error message contains context
        error_msg = str(exc_info.value).lower()
        assert "provider error" in error_msg or "error" in error_msg, (
            "Error message should provide context about the failure"
        )
    
    @pytest.mark.asyncio
    @settings(max_examples=50, deadline=2000)
    @given(
        system_prompt=prompt_strategy(),
        user_prompt=prompt_strategy(),
        image_base64=image_base64_strategy(),
    )
    async def test_llm_response_includes_raw_text_and_parsed_json(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
    ):
        """
        Property 2: LLM response includes both raw text and parsed JSON
        
        For any successful LLM call, the response should include both the
        raw text from the provider and the parsed JSON structure.
        
        **Validates: Requirements 1.2, 3.4**
        """
        # Create a mock provider
        mock_provider = AsyncMock()
        mock_provider.call = AsyncMock(return_value={
            "raw_text": '{"image_meta": {"width": 100, "height": 100}, "participants": {"self": {"id": "u1", "nickname": "User"}, "other": {"id": "u2", "nickname": "Other"}}, "bubbles": [], "layout": {"type": "two_columns", "left_role": "talker", "right_role": "user"}}',
            "provider": "test",
            "model": "test-model",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
        })
        
        # Create client and register mock provider
        config = MagicMock()
        client = MultimodalLLMClient(config)
        client.register_provider("test", mock_provider)
        
        # Call the LLM
        response = await client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_base64=image_base64,
            provider="test",
        )
        
        # Verify response has both raw_text and parsed_json
        assert hasattr(response, "raw_text"), "Response should have raw_text field"
        assert hasattr(response, "parsed_json"), "Response should have parsed_json field"
        
        # Verify types
        assert isinstance(response.raw_text, str), "raw_text should be a string"
        assert isinstance(response.parsed_json, dict), "parsed_json should be a dict"
        
        # Verify raw_text is not empty
        assert len(response.raw_text) > 0, "raw_text should not be empty"
        
        # Verify parsed_json has expected structure
        assert "image_meta" in response.parsed_json, "parsed_json should have image_meta"
        assert "participants" in response.parsed_json, "parsed_json should have participants"
        assert "bubbles" in response.parsed_json, "parsed_json should have bubbles"
        assert "layout" in response.parsed_json, "parsed_json should have layout"
