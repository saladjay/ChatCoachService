"""LLM Adapter - Unified LLM calling interface using over-seas-llm-platform-service.

This module provides a unified interface for calling various LLM providers
through the over-seas-llm-platform-service library.

Requirements: 3.3
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

import httpx

from app.models.schemas import (
    LLMResult,
    ReplyGenerationInput,
)
from app.models.screenshot import MultimodalLLMResponse
from app.services.base import BaseReplyGenerator

# Add llm_adapter to path
LLM_ADAPTER_PATH = Path(__file__).parent.parent.parent / "core" / "llm_adapter"
if str(LLM_ADAPTER_PATH) not in sys.path:
    sys.path.insert(0, str(LLM_ADAPTER_PATH))

from llm_adapter import (
    LLMAdapter as OverSeasLLMAdapter,
    LLMRequest,
    LLMAdapterError,
    ConfigManager,
)
from llm_adapter.adapters.base import (
    MultimodalContent,
    ImageInput,
    ImageInputType,
)
from llm_adapter.adapters import (
    DashScopeAdapter,
    OpenRouterAdapter,
    GeminiAdapter,
    OpenAIAdapter,
)


# Quality mapping: chatcoach quality -> over-seas-llm-platform-service quality
QUALITY_MAP = {
    "cheap": "low",
    "normal": "medium",
    "premium": "high",
}

# Task type to scene mapping
TASK_SCENE_MAP = {
    "scene": "system",
    "persona": "persona",
    "generation": "chat",
    "qc": "coach",
    "strategy_planning": "system",
}

# 支持的平台列�?
SUPPORTED_PROVIDERS = ["openai", "gemini", "cloudflare", "huggingface", "dashscope", "openrouter"]

# Provider name to adapter class mapping
ADAPTER_CLASSES = {
    "dashscope": DashScopeAdapter,
    "openrouter": OpenRouterAdapter,
    "gemini": GeminiAdapter,
    "openai": OpenAIAdapter,
}


def _get_adapter_class(provider: str):
    """Get adapter class for a provider.
    
    Args:
        provider: Provider name
        
    Returns:
        Adapter class
        
    Raises:
        ValueError: If provider is not supported
    """
    adapter_class = ADAPTER_CLASSES.get(provider)
    if not adapter_class:
        raise ValueError(f"No adapter class found for provider: {provider}")
    return adapter_class


class LLMCall:
    """Represents a single LLM call request."""
    
    def __init__(
        self,
        task_type: Literal["screenshot_parse","context_builder", "scene", "persona", "generation", "qc", "strategy_planning"],
        prompt: str,
        quality: Literal["cheap", "normal", "premium"] = "normal",
        user_id: str = "system",
        provider: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,  # Phase 3: Token limit
    ):
        """Initialize LLM call request.
        
        Args:
            task_type: Task type for scene mapping
            prompt: The prompt to send to LLM
            quality: Quality tier (cheap/normal/premium)
            user_id: User ID for billing/logging
            provider: Optional specific provider (e.g., 'dashscope', 'openai')
            model: Optional specific model (required if provider is specified)
            max_tokens: Optional maximum tokens for output (Phase 3)
        """
        self.task_type = task_type
        self.prompt = prompt
        self.quality = quality
        self.user_id = user_id
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens  # Phase 3


class BaseLLMAdapter:
    """Abstract base class for LLM Adapter."""
    
    async def call(self, llm_call: LLMCall) -> LLMResult:
        """Make an LLM call."""
        raise NotImplementedError
    
    async def call_with_provider(
        self,
        prompt: str,
        provider: str,
        model: str,
        user_id: str = "system",
        max_tokens: int | None = None,  # Phase 3
    ) -> LLMResult:
        """Make an LLM call with specific provider and model."""
        raise NotImplementedError


class LLMAdapterImpl(BaseLLMAdapter):
    """LLM Adapter implementation using over-seas-llm-platform-service.
    
    This implementation wraps the OverSeasLLMAdapter to provide:
    - Model selection based on quality tier
    - Provider abstraction (OpenAI, Gemini, Cloudflare, DashScope, etc.)
    - Direct provider/model specification
    - Token counting and cost calculation
    - Automatic fallback on provider failure
    
    Requirements: 3.3
    """
    
    def __init__(self, config_path: str | None = None):
        """Initialize the LLM Adapter.
        
        Args:
            config_path: Path to config.yaml. Defaults to core/llm_adapter/config.yaml
        """
        if config_path is None:
            config_path = str(LLM_ADAPTER_PATH / "config.yaml")
        
        self._adapter = OverSeasLLMAdapter(config_path=config_path)
    
    @property
    def adapter(self) -> OverSeasLLMAdapter:
        """Get the underlying OverSeasLLMAdapter instance."""
        return self._adapter
    
    async def call(self, llm_call: LLMCall) -> LLMResult:
        """Make an LLM call using over-seas-llm-platform-service.
        
        If provider and model are specified in llm_call, uses direct provider call.
        Otherwise, uses quality-based routing.
        
        Args:
            llm_call: The LLM call request.
        
        Returns:
            LLMResult with generated text and metadata.
        
        Raises:
            LLMAdapterError: If all providers fail.
        
        Note:
            Phase 3: max_tokens parameter is stored but not yet enforced by
            the underlying adapter. This will be implemented when the
            over-seas-llm-platform-service supports max_tokens.
        """
        # 如果指定�?provider �?model，直接调�?
        if llm_call.provider and llm_call.model:
            return await self.call_with_provider(
                prompt=llm_call.prompt,
                provider=llm_call.provider,
                model=llm_call.model,
                user_id=llm_call.user_id,
                max_tokens=llm_call.max_tokens,  # Phase 3: Pass through
            )
        
        # 否则使用 quality-based routing
        quality = QUALITY_MAP.get(llm_call.quality, "medium")
        scene = TASK_SCENE_MAP.get(llm_call.task_type, "chat")
        
        # Phase 3: Note max_tokens for future implementation
        # TODO: Pass max_tokens to adapter.generate() when supported
        
        response = await self._adapter.generate(
            user_id=llm_call.user_id,
            prompt=llm_call.prompt,
            scene=scene,
            quality=quality,
        )
        
        return LLMResult(
            text=response.text,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
        )
    
    async def call_with_provider(
        self,
        prompt: str,
        provider: str,
        model: str,
        user_id: str = "system",
        max_tokens: int | None = None,  # Phase 3: Token limit
    ) -> LLMResult:
        """Make an LLM call with specific provider and model.
        
        This bypasses the quality-based routing and directly calls
        the specified provider/model combination.
        
        Args:
            prompt: The prompt to send to LLM
            provider: Provider name (e.g., 'dashscope', 'openai', 'gemini')
            model: Model name (e.g., 'qwen-plus', 'gpt-4o', 'gemini-1.5-flash')
            user_id: User ID for billing/logging
            max_tokens: Optional maximum tokens for output (Phase 3)
        
        Returns:
            LLMResult with generated text and metadata.
        
        Raises:
            ValueError: If provider is not supported
            LLMAdapterError: If the provider call fails
        
        Note:
            Phase 3: max_tokens parameter is stored but not yet enforced by
            the underlying adapter.
        """
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported providers: {SUPPORTED_PROVIDERS}"
            )
        
        # Phase 3: Note max_tokens for future implementation
        # TODO: Pass max_tokens to adapter.generate_with_provider() when supported
        
        response = await self._adapter.generate_with_provider(
            user_id=user_id,
            prompt=prompt,
            provider=provider,
            model=model,
        )
        
        return LLMResult(
            text=response.text,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
        )
    
    def get_user_usage(self, user_id: str) -> dict:
        """Get usage statistics for a user."""
        return self._adapter.get_user_usage(user_id)
    
    def reset_router_availability(self) -> None:
        """Reset all providers to available status."""
        self._adapter.reset_router_availability()
    
    def mark_provider_unavailable(self, provider: str) -> None:
        """Mark a provider as temporarily unavailable."""
        self._adapter.mark_provider_unavailable(provider)
    
    def mark_provider_available(self, provider: str) -> None:
        """Mark a provider as available again."""
        self._adapter.mark_provider_available(provider)
    
    def get_available_providers(
        self,
        quality: Literal["cheap", "normal", "premium"] | None = None,
    ) -> list[tuple[str, str]] | list[str]:
        """Get list of available providers.
        
        Args:
            quality: Optional quality level. If provided, returns (provider, model) tuples.
        
        Returns:
            List of provider names or (provider, model) tuples
        """
        if quality:
            mapped_quality = QUALITY_MAP.get(quality, "medium")
            return self._adapter.get_available_providers(mapped_quality)
        return self._adapter.get_available_providers()
    
    def get_provider_models(self, provider: str) -> dict[str, str]:
        """Get all available models for a provider.
        
        Args:
            provider: Provider name
        
        Returns:
            Dictionary mapping tier names to model names
        """
        return self._adapter.get_provider_models(provider)
    
    async def call_multimodal(
        self,
        prompt: str,
        image_data: str,
        image_type: Literal["url", "base64"] = "base64",
        provider: str | None = None,
        model: str | None = None,
        user_id: str = "system",
        mime_type: str = "image/jpeg",
    ) -> LLMResult:
        """Make a multimodal LLM call with text and image.
        
        This method supports two image input formats:
        - URL: Provide image via URL (image_type="url")
        - Base64: Provide image as base64-encoded string (image_type="base64")
        
        Args:
            prompt: The text prompt to send to LLM
            image_data: Image URL or base64-encoded string
            image_type: Type of image input ("url" or "base64")
            provider: Optional specific provider (e.g., 'dashscope', 'openrouter')
            model: Optional specific model (required if provider is specified)
            user_id: User ID for billing/logging
            mime_type: MIME type of the image (e.g., "image/jpeg", "image/png")
        
        Returns:
            LLMResult with generated text and metadata.
        
        Raises:
            ValueError: If provider is not supported or doesn't support multimodal
            LLMAdapterError: If the provider call fails
        
        Example:
            # Using base64 image
            result = await adapter.call_multimodal(
                prompt="What's in this image?",
                image_data=base64_string,
                image_type="base64",
                provider="dashscope",
                model="qwen-vl-plus"
            )
            
            # Using image URL
            result = await adapter.call_multimodal(
                prompt="Describe this image",
                image_data="https://example.com/image.jpg",
                image_type="url",
                provider="openrouter",
                model="openai/gpt-4o"
            )
        """
        # Create ImageInput based on type
        if image_type == "url":
            image_input = ImageInput.from_url(image_data)
        elif image_type == "base64":
            image_input = ImageInput.from_base64(image_data, mime_type)
        else:
            raise ValueError(f"Invalid image_type: {image_type}. Must be 'url' or 'base64'")
        
        # Create MultimodalContent
        content = MultimodalContent(
            text=prompt,
            images=[image_input]
        )
        
        # If provider and model are specified, use them directly
        if provider and model:
            if provider not in SUPPORTED_PROVIDERS:
                raise ValueError(
                    f"Unsupported provider: {provider}. "
                    f"Supported providers: {SUPPORTED_PROVIDERS}"
                )
            
            # Get the provider adapter
            provider_config = self._adapter.config_manager.get_provider_config(provider)
            adapter_class = _get_adapter_class(provider)
            
            # Create adapter instance with config
            adapter_kwargs = {
                "api_key": provider_config.api_key,
            }
            
            # Add provider-specific config
            if hasattr(provider_config, 'base_url') and provider_config.base_url:
                adapter_kwargs['base_url'] = provider_config.base_url
            if hasattr(provider_config, 'mode') and provider_config.mode:
                adapter_kwargs['mode'] = provider_config.mode
            if hasattr(provider_config, 'project_id') and provider_config.project_id:
                adapter_kwargs['project_id'] = provider_config.project_id
            if hasattr(provider_config, 'location') and provider_config.location:
                adapter_kwargs['location'] = provider_config.location
            
            adapter = adapter_class(**adapter_kwargs)
            
            try:
                # Call multimodal generation
                raw_result = await adapter.generate_multimodal(content, model)
                
                # Calculate cost if not provided
                cost_usd = raw_result.cost_usd
                if cost_usd is None and raw_result.input_tokens and raw_result.output_tokens:
                    try:
                        cost_usd = self._adapter.billing.calculate_cost(
                            provider=provider,
                            model=model,
                            input_tokens=raw_result.input_tokens,
                            output_tokens=raw_result.output_tokens,
                        )
                    except Exception:
                        cost_usd = 0.0
                
                return LLMResult(
                    text=raw_result.text,
                    provider=provider,
                    model=model,
                    input_tokens=raw_result.input_tokens or 0,
                    output_tokens=raw_result.output_tokens or 0,
                    cost_usd=cost_usd or 0.0,
                )
            finally:
                await adapter.aclose()
        
        # Otherwise, use default multimodal provider
        # Check if quality routing is disabled
        import os
        disable_routing = os.environ.get("LLM_DISABLE_QUALITY_ROUTING", "").lower() == "true"
        
        if disable_routing:
            # Use default provider only, no fallback
            try:
                default_provider = self._adapter.config_manager.get_default_provider()
                provider_config = self._adapter.config_manager.get_provider_config(default_provider)
                multimodal_model = provider_config.models.multimodal
                
                if not multimodal_model:
                    raise RuntimeError(
                        f"Default provider '{default_provider}' has no multimodal model configured. "
                        f"Please configure a multimodal model for '{default_provider}' in config.yaml"
                    )
                
                # Check API key
                api_key = (provider_config.api_key or "").strip()
                if not api_key and default_provider != "gemini":
                    raise RuntimeError(f"Default provider '{default_provider}' has no API key configured")
                
                # Use default provider
                return await self.call_multimodal(
                    prompt=prompt,
                    image_data=image_data,
                    image_type=image_type,
                    provider=default_provider,
                    model=multimodal_model,
                    user_id=user_id,
                    mime_type=mime_type,
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to use default provider '{default_provider}' for multimodal (routing disabled): {str(e)}"
                )
        
        # Quality routing enabled - try multiple providers
        multimodal_providers = ["openrouter", "dashscope", "gemini", "openai"]
        
        errors = []  # Collect errors for debugging
        
        for provider_name in multimodal_providers:
            try:
                provider_config = self._adapter.config_manager.get_provider_config(provider_name)
                multimodal_model = provider_config.models.multimodal
                
                if not multimodal_model:
                    errors.append(f"{provider_name}: No multimodal model configured")
                    continue
                
                # Check if provider has API key (except Gemini vertex mode)
                api_key = (provider_config.api_key or "").strip()
                if not api_key and provider_name != "gemini":
                    errors.append(f"{provider_name}: No API key configured")
                    continue
                
                # For Gemini, check if it's vertex mode
                if provider_name == "gemini" and not api_key:
                    if not (hasattr(provider_config, 'mode') and provider_config.mode == 'vertex'):
                        errors.append(f"{provider_name}: No API key and not in vertex mode")
                        continue
                
                # Found a valid provider, use it
                return await self.call_multimodal(
                    prompt=prompt,
                    image_data=image_data,
                    image_type=image_type,
                    provider=provider_name,
                    model=multimodal_model,
                    user_id=user_id,
                    mime_type=mime_type,
                )
            except Exception as e:
                errors.append(f"{provider_name}: {str(e)}")
                continue
        
        # All providers failed, provide detailed error message
        error_details = "\n".join(f"  - {err}" for err in errors)
        raise RuntimeError(
            f"No multimodal provider available. Tried all providers:\n{error_details}\n\n"
            "Please configure a provider with a 'multimodal' model and valid API key "
            "in core/llm_adapter/config.yaml"
        )
    
    async def call_multimodal_with_multiple_images(
        self,
        prompt: str,
        images: list[tuple[str, Literal["url", "base64"]]],
        provider: str | None = None,
        model: str | None = None,
        user_id: str = "system",
        mime_type: str = "image/jpeg",
    ) -> LLMResult:
        """Make a multimodal LLM call with text and multiple images.
        
        Args:
            prompt: The text prompt to send to LLM
            images: List of (image_data, image_type) tuples
            provider: Optional specific provider
            model: Optional specific model
            user_id: User ID for billing/logging
            mime_type: MIME type of the images
        
        Returns:
            LLMResult with generated text and metadata.
        
        Example:
            result = await adapter.call_multimodal_with_multiple_images(
                prompt="Compare these images",
                images=[
                    (base64_string1, "base64"),
                    ("https://example.com/image2.jpg", "url"),
                ],
                provider="openrouter",
                model="openai/gpt-4o"
            )
        """
        # Create ImageInput list
        image_inputs = []
        for image_data, image_type in images:
            if image_type == "url":
                image_inputs.append(ImageInput.from_url(image_data))
            elif image_type == "base64":
                image_inputs.append(ImageInput.from_base64(image_data, mime_type))
            else:
                raise ValueError(f"Invalid image_type: {image_type}. Must be 'url' or 'base64'")
        
        # Create MultimodalContent
        content = MultimodalContent(
            text=prompt,
            images=image_inputs
        )
        
        # If provider and model are specified, use them directly
        if provider and model:
            if provider not in SUPPORTED_PROVIDERS:
                raise ValueError(
                    f"Unsupported provider: {provider}. "
                    f"Supported providers: {SUPPORTED_PROVIDERS}"
                )
            
            # Get the provider adapter
            provider_config = self._adapter.config_manager.get_provider_config(provider)
            adapter_class = _get_adapter_class(provider)
            
            # Create adapter instance with config
            adapter_kwargs = {
                "api_key": provider_config.api_key,
            }
            
            # Add provider-specific config
            if hasattr(provider_config, 'base_url') and provider_config.base_url:
                adapter_kwargs['base_url'] = provider_config.base_url
            if hasattr(provider_config, 'mode') and provider_config.mode:
                adapter_kwargs['mode'] = provider_config.mode
            if hasattr(provider_config, 'project_id') and provider_config.project_id:
                adapter_kwargs['project_id'] = provider_config.project_id
            if hasattr(provider_config, 'location') and provider_config.location:
                adapter_kwargs['location'] = provider_config.location
            
            adapter = adapter_class(**adapter_kwargs)
            
            try:
                # Call multimodal generation
                raw_result = await adapter.generate_multimodal(content, model)
                
                # Calculate cost if not provided
                cost_usd = raw_result.cost_usd
                if cost_usd is None and raw_result.input_tokens and raw_result.output_tokens:
                    try:
                        cost_usd = self._adapter.billing.calculate_cost(
                            provider=provider,
                            model=model,
                            input_tokens=raw_result.input_tokens,
                            output_tokens=raw_result.output_tokens,
                        )
                    except Exception:
                        cost_usd = 0.0
                
                return LLMResult(
                    text=raw_result.text,
                    provider=provider,
                    model=model,
                    input_tokens=raw_result.input_tokens or 0,
                    output_tokens=raw_result.output_tokens or 0,
                    cost_usd=cost_usd or 0.0,
                )
            finally:
                await adapter.aclose()
        
        # Otherwise, use default multimodal provider
        multimodal_providers = ["openrouter", "dashscope", "gemini", "openai"]
        
        for provider_name in multimodal_providers:
            try:
                provider_config = self._adapter.config_manager.get_provider_config(provider_name)
                multimodal_model = provider_config.models.multimodal
                
                if not multimodal_model:
                    continue
                
                # Check if provider has API key (except Gemini vertex mode)
                api_key = (provider_config.api_key or "").strip()
                if not api_key and provider_name != "gemini":
                    continue
                
                # Found a valid provider, use it
                return await self.call_multimodal_with_multiple_images(
                    prompt=prompt,
                    images=images,
                    provider=provider_name,
                    model=multimodal_model,
                    user_id=user_id,
                    mime_type=mime_type,
                )
            except Exception:
                continue
        
        raise RuntimeError(
            "No multimodal provider available. Please configure a provider "
            "with a 'multimodal' model in core/llm_adapter/config.yaml"
        )





# Default instance factory
def create_llm_adapter(config_path: str | None = None) -> LLMAdapterImpl:
    """Create a new LLM Adapter instance.
    
    Args:
        config_path: Optional path to config.yaml
    
    Returns:
        LLMAdapterImpl instance
    """
    return LLMAdapterImpl(config_path=config_path)
