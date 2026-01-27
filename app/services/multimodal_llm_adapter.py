"""Multimodal LLM adapter for vision-capable language model APIs.

This module provides the MultimodalLLMClient class that uses the unified
LLM adapter (core/llm_adapter) for multimodal vision calls.

The adapter supports multiple providers through OpenRouter:
- Qwen VL models (qwen/qwen-2.5-vl-7b-instruct, qwen/qwen3-vl-30b-a3b-instruct)
- Google Gemini (google/gemini-2.5-flash)
- OpenAI GPT-4o (openai/gpt-4o)
- And other vision-capable models available on OpenRouter

Configuration is managed through core/llm_adapter/config.yaml
"""

import base64
import json
import re
from pathlib import Path
import sys

import httpx

from app.models.screenshot import MultimodalLLMResponse

# Add llm_adapter to path
LLM_ADAPTER_PATH = Path(__file__).parent.parent.parent / "core" / "llm_adapter"
if str(LLM_ADAPTER_PATH) not in sys.path:
    sys.path.insert(0, str(LLM_ADAPTER_PATH))

from llm_adapter import LLMAdapter, ConfigManager


class MultimodalLLMClient:
    """Client for calling multimodal (vision) LLM APIs using unified LLM adapter.
    
    This client uses the core/llm_adapter infrastructure to call vision-capable
    models through OpenRouter, which provides access to multiple vision models:
    - Qwen VL models (cost-effective, good quality)
    - Google Gemini (fast, good for general use)
    - OpenAI GPT-4o (premium quality)
    - And other vision models
    
    Configuration is managed through core/llm_adapter/config.yaml
    """

    def __init__(self, config=None, config_path: str | None = None):
        """Initialize the multimodal LLM client.
        
        Args:
            config: Legacy config parameter (ignored, kept for compatibility)
            config_path: Optional path to config.yaml (defaults to core/llm_adapter/config.yaml)
        """
        # Initialize config manager and LLM adapter
        if config_path is None:
            config_path = str(LLM_ADAPTER_PATH / "config.yaml")
        
        self._config_manager = ConfigManager(config_path)
        self._llm_adapter = LLMAdapter(config_manager=self._config_manager)
        
        # Get multimodal model from config by reading YAML directly
        # (ModelConfig doesn't include multimodal field, so we read it manually)
        self._provider = None
        self._model = None
        
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
            
            providers_config = raw_config.get('providers', {})
            
            # Priority: default provider > gemini > dashscope > openrouter > openai
            default_provider = raw_config.get('llm', {}).get('default_provider', 'openrouter')
            
            # Try default provider first
            if default_provider in providers_config:
                provider_data = providers_config[default_provider]
                if isinstance(provider_data, dict):
                    models = provider_data.get('models', {})
                    if isinstance(models, dict) and 'multimodal' in models:
                        api_key = provider_data.get('api_key', '')
                        # Check if API key is set (not empty and not an env var placeholder)
                        if api_key and not api_key.startswith('${'):
                            self._provider = default_provider
                            self._model = models['multimodal']
            
            # Fallback to gemini
            if not self._model and 'gemini' in providers_config:
                provider_data = providers_config['gemini']
                if isinstance(provider_data, dict):
                    models = provider_data.get('models', {})
                    if isinstance(models, dict) and 'multimodal' in models:
                        api_key = provider_data.get('api_key', '')
                        if api_key and not api_key.startswith('${'):
                            self._provider = 'gemini'
                            self._model = models['multimodal']
            
            # Fallback to dashscope
            if not self._model and 'dashscope' in providers_config:
                provider_data = providers_config['dashscope']
                if isinstance(provider_data, dict):
                    models = provider_data.get('models', {})
                    if isinstance(models, dict) and 'multimodal' in models:
                        api_key = provider_data.get('api_key', '')
                        if api_key and not api_key.startswith('${'):
                            self._provider = 'dashscope'
                            self._model = models['multimodal']
            
            # Fallback to openrouter
            if not self._model and 'openrouter' in providers_config:
                provider_data = providers_config['openrouter']
                if isinstance(provider_data, dict):
                    models = provider_data.get('models', {})
                    if isinstance(models, dict) and 'multimodal' in models:
                        api_key = provider_data.get('api_key', '')
                        if api_key and not api_key.startswith('${'):
                            self._provider = 'openrouter'
                            self._model = models['multimodal']
            
            # Fallback to openai
            if not self._model and 'openai' in providers_config:
                provider_data = providers_config['openai']
                if isinstance(provider_data, dict):
                    models = provider_data.get('models', {})
                    if isinstance(models, dict) and 'multimodal' in models:
                        api_key = provider_data.get('api_key', '')
                        if api_key and not api_key.startswith('${'):
                            self._provider = 'openai'
                            self._model = models['multimodal']
        
        except Exception as e:
            # If we can't read the config, raise an error
            raise RuntimeError(f"Failed to load multimodal configuration: {e}")
        
        if not self._provider or not self._model:
            raise RuntimeError(
                "No multimodal model configured. Please configure a provider "
                "with a 'multimodal' model and valid API key in core/llm_adapter/config.yaml"
            )


    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
        provider: str | None = None,
    ) -> MultimodalLLMResponse:
        """Call multimodal LLM with image and prompts.
        
        This method uses OpenRouter (or configured provider) to call vision models.
        The API follows OpenAI's format for multimodal requests.
        
        Args:
            system_prompt: System-level instructions
            user_prompt: User-level instructions
            image_base64: Base64-encoded image data
            provider: Optional specific provider to use (overrides default)
            
        Returns:
            MultimodalLLMResponse with parsed results and metadata
            
        Raises:
            RuntimeError: If LLM call fails
        """
        # Use specified provider or default
        selected_provider = provider if provider else self._provider
        selected_model = self._model
        
        # If provider is specified, get its multimodal model
        if provider and provider != self._provider:
            try:
                provider_config = self._config_manager.get_provider_config(provider)
                if provider_config and provider_config.models:
                    selected_model = provider_config.models.get("multimodal")
                    if not selected_model:
                        raise RuntimeError(f"Provider '{provider}' has no multimodal model configured")
            except Exception as e:
                raise RuntimeError(f"Failed to get provider config: {e}")
        
        # Call the vision API using OpenRouter-compatible format
        try:
            response_dict = await self._call_vision_api(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_base64=image_base64,
                provider=selected_provider,
                model=selected_model,
            )
        except Exception as e:
            raise RuntimeError(f"Vision API call failed: {e}")
        
        # Parse JSON from response
        try:
            parsed_json = self._parse_json_response(response_dict["raw_text"])
        except ValueError as e:
            raise RuntimeError(f"Failed to parse JSON from LLM response: {e}")
        
        # Create MultimodalLLMResponse
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
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
        provider: str,
        model: str,
    ) -> dict:
        """Call vision API using OpenRouter-compatible format.
        
        Args:
            system_prompt: System-level instructions
            user_prompt: User-level instructions
            image_base64: Base64-encoded image data
            provider: Provider name
            model: Model name
            
        Returns:
            Dictionary with raw_text, provider, model, input_tokens, output_tokens, cost_usd
            
        Raises:
            RuntimeError: If API call fails
        """
        # Get provider config
        provider_config = self._config_manager.get_provider_config(provider)
        api_key = provider_config.api_key
        base_url = provider_config.base_url or "https://openrouter.ai/api/v1"
        
        # Construct messages with vision content (OpenAI-compatible format)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.0,  # Deterministic for structured output
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        # Call API
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload
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
        
        # Extract response data
        try:
            raw_text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected response format: {e}")
        
        # Get token usage
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        
        # Try to get actual cost from response
        cost_usd = usage.get("total_cost") or usage.get("cost")
        if cost_usd is None:
            # Fallback to billing engine calculation
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
        """Extract and parse JSON from LLM response.
        
        This method handles multiple formats:
        1. Direct JSON response
        2. JSON wrapped in markdown code blocks (```json ... ```)
        3. JSON embedded in text
        
        Args:
            raw_text: Raw text response from LLM
            
        Returns:
            Parsed JSON dictionary
            
        Raises:
            ValueError: If JSON cannot be extracted or parsed
        """
        # Try direct JSON parse first
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        # Pattern: ```json ... ``` or ``` ... ```
        code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        matches = re.findall(code_block_pattern, raw_text, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
        
        # Try to find JSON object in text (look for { ... })
        json_pattern = r"\{.*\}"
        matches = re.findall(json_pattern, raw_text, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        # If all attempts fail, raise error
        raise ValueError(f"Could not extract valid JSON from response: {raw_text[:200]}...")

