"""LLM Adapter - Unified LLM calling interface using over-seas-llm-platform-service.

This module provides a unified interface for calling various LLM providers
through the over-seas-llm-platform-service library.

Requirements: 3.3
"""

import json
import re
import sys
from pathlib import Path
from typing import Literal

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


class MultimodalLLMClient:
    def __init__(self, config=None, config_path: str | None = None):
        if config_path is None:
            config_path = str(LLM_ADAPTER_PATH / "config.yaml")

        self._config_manager = ConfigManager(config_path)
        self._llm_adapter = OverSeasLLMAdapter(config_manager=self._config_manager)

        self._provider: str | None = None
        self._model: str | None = None

        try:
            default_provider = self._config_manager.get_default_provider()
        except Exception:
            default_provider = "openrouter"

        provider_priority = [default_provider, "gemini", "dashscope", "openrouter", "openai"]
        seen: set[str] = set()
        ordered_providers: list[str] = []
        for p in provider_priority:
            if p and p not in seen:
                ordered_providers.append(p)
                seen.add(p)

        last_error: Exception | None = None
        for provider_name in ordered_providers:
            try:
                provider_config = self._config_manager.get_provider_config(provider_name)
                multimodal_model = provider_config.models.multimodal
                if not multimodal_model:
                    continue

                api_key = (provider_config.api_key or "").strip()
                if not api_key:
                    continue

                self._provider = provider_name
                self._model = multimodal_model
                break
            except Exception as e:
                last_error = e
                continue

        if last_error is not None and (not self._provider or not self._model):
            raise RuntimeError(f"Failed to load multimodal configuration: {last_error}")

        if not self._provider or not self._model:
            raise RuntimeError(
                "No multimodal model configured. Please configure a provider "
                "with a 'multimodal' model and valid API key in core/llm_adapter/config.yaml"
            )

    async def call(
        self,
        prompt: str,
        image_base64: str,
        provider: str | None = None,
    ) -> MultimodalLLMResponse:
        selected_provider = provider if provider else self._provider
        selected_model = self._model

        if provider and provider != self._provider:
            try:
                provider_config = self._config_manager.get_provider_config(provider)
                multimodal_model = provider_config.models.multimodal
                if not multimodal_model:
                    raise RuntimeError(f"Provider '{provider}' has no multimodal model configured")
                selected_model = multimodal_model
            except Exception as e:
                raise RuntimeError(f"Failed to get provider config: {e}")

        try:
            response_dict = await self._call_vision_api(
                prompt=prompt,
                image_base64=image_base64,
                provider=selected_provider,
                model=selected_model,
            )
        except Exception as e:
            raise RuntimeError(f"Vision API call failed: {e}")

        try:
            parsed_json = self._parse_json_response(response_dict["raw_text"])
        except ValueError as e:
            raise RuntimeError(f"Failed to parse JSON from LLM response: {e}")

        return MultimodalLLMResponse(
            raw_text=response_dict["raw_text"],
            parsed_json=parsed_json,
            provider=response_dict["provider"],
            model=response_dict["model"],
            input_tokens=response_dict["input_tokens"],
            output_tokens=response_dict["output_tokens"],
            cost_usd=response_dict["cost_usd"],
        )

    async def _call_vision_api(
        self,
        prompt: str,
        image_base64: str,
        provider: str,
        model: str,
    ) -> dict:
        provider_config = self._config_manager.get_provider_config(provider)
        api_key = provider_config.api_key
        base_url = provider_config.base_url

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": prompt,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                        }
                    ],
                },
            ],
            "max_tokens": 4096,
            "temperature": 0.0,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as e:
            raise RuntimeError(f"Request timed out: {e}")
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", {}).get("message", e.response.text)
            except Exception:
                error_detail = e.response.text
            raise RuntimeError(f"API error: {error_detail}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {e}")

        try:
            raw_text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected response format: {e}")

        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        cost_usd = usage.get("total_cost") or usage.get("cost")
        if cost_usd is None:
            try:
                cost_usd = self._llm_adapter.billing.calculate_cost(
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            except Exception:
                cost_usd = 0.0
        else:
            cost_usd = float(cost_usd)

        return {
            "raw_text": raw_text,
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
        }

    def _parse_json_response(self, raw_text: str) -> dict:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        matches = re.findall(code_block_pattern, raw_text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        json_pattern = r"\{.*\}"
        matches = re.findall(json_pattern, raw_text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        raise ValueError(f"Could not extract valid JSON from response: {raw_text[:200]}...")





# Default instance factory
def create_llm_adapter(config_path: str | None = None) -> LLMAdapterImpl:
    """Create a new LLM Adapter instance.
    
    Args:
        config_path: Optional path to config.yaml
    
    Returns:
        LLMAdapterImpl instance
    """
    return LLMAdapterImpl(config_path=config_path)
