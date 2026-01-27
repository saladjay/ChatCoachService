"""LLM Adapter - Unified LLM calling interface using over-seas-llm-platform-service.

This module provides a unified interface for calling various LLM providers
through the over-seas-llm-platform-service library.

Requirements: 3.3
"""

import sys
from pathlib import Path
from typing import Literal

from app.models.schemas import (
    LLMResult,
    ReplyGenerationInput,
)
from app.services.base import BaseReplyGenerator

# Add llm_adapter to path
LLM_ADAPTER_PATH = Path(__file__).parent.parent.parent / "core" / "llm_adapter"
if str(LLM_ADAPTER_PATH) not in sys.path:
    sys.path.insert(0, str(LLM_ADAPTER_PATH))

from llm_adapter import LLMAdapter as OverSeasLLMAdapter, LLMRequest, LLMAdapterError


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

# 支持的平台列表
SUPPORTED_PROVIDERS = ["openai", "gemini", "cloudflare", "huggingface", "dashscope", "openrouter"]


class LLMCall:
    """Represents a single LLM call request."""
    
    def __init__(
        self,
        task_type: Literal["scene", "persona", "generation", "qc", "strategy_planning"],
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
        # 如果指定了 provider 和 model，直接调用
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





# Default instance factory
def create_llm_adapter(config_path: str | None = None) -> LLMAdapterImpl:
    """Create a new LLM Adapter instance.
    
    Args:
        config_path: Optional path to config.yaml
    
    Returns:
        LLMAdapterImpl instance
    """
    return LLMAdapterImpl(config_path=config_path)
