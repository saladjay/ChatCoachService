# Multimodal LLM Adapter Refactoring

## Overview

Refactored `app/services/multimodal_llm_adapter.py` to use the unified LLM adapter infrastructure from `core/llm_adapter` instead of directly calling third-party APIs (OpenAI, Gemini, Claude, Anthropic).

## Changes Made

### Before
- Directly imported and used third-party libraries:
  - `openai` (AsyncOpenAI)
  - `google.generativeai` (Gemini)
  - `anthropic` (AsyncAnthropic)
- Each provider had its own implementation class
- API keys managed through environment variables
- Cost calculation duplicated in each provider

### After
- Uses unified `core/llm_adapter` infrastructure
- Configuration managed through `core/llm_adapter/config.yaml`
- Single implementation using OpenRouter-compatible API format
- Leverages existing billing engine for cost calculation
- Supports all providers configured in the unified adapter

## Benefits

1. **Unified Configuration**: All LLM providers (text and vision) configured in one place
2. **Consistent Billing**: Uses the same billing engine for cost tracking
3. **Reduced Dependencies**: No need for provider-specific libraries (openai, google-generativeai, anthropic)
4. **Better Maintainability**: Single code path for all vision providers
5. **Logging Integration**: Can easily integrate with `LoggingLLMAdapter` for unified logging

## Configuration

The multimodal adapter now reads from `core/llm_adapter/config.yaml`:

```yaml
llm:
  default_provider: openrouter

providers:
  openrouter:
    api_key: ${OPENROUTER_API_KEY}
    base_url: https://openrouter.ai/api/v1
    models:
      cheap: google/gemini-2.0-flash-001
      normal: google/gemini-2.5-flash
      premium: google/gemini-3-flash-preview
      multimodal: qwen/qwen3-vl-30b-a3b-instruct  # Vision model

  gemini:
    api_key: ${GOOGLE_API_KEY}
    models:
      multimodal: gemini-2.5-flash  # Vision model

  openai:
    api_key: ${OPENAI_API_KEY}
    models:
      multimodal: gpt-4o  # Vision model
```

## Provider Selection

The adapter automatically selects a multimodal provider in this priority order:
1. Default provider (if it has a multimodal model)
2. OpenRouter (if configured)
3. Gemini (if configured)
4. OpenAI (if configured)

You can also specify a provider explicitly:

```python
response = await client.call(
    prompt="...",
    image_base64="...",
    provider="gemini"  # Use specific provider
)
```

## API Compatibility

The public API remains unchanged:

```python
from app.services.llm_adapter import MultimodalLLMClient

client = MultimodalLLMClient()

response = await client.call(
    prompt="You are a helpful assistant",
    image_base64="base64_encoded_image_data"
)

print(response.parsed_json)
print(f"Cost: ${response.cost_usd}")
```

## Supported Models

Through OpenRouter, the adapter now supports:
- **Qwen VL**: `qwen/qwen-2.5-vl-7b-instruct`, `qwen/qwen3-vl-30b-a3b-instruct`
- **Google Gemini**: `google/gemini-2.5-flash`, `google/gemini-2.0-flash-001`
- **OpenAI**: `openai/gpt-4o`, `openai/gpt-4-turbo`
- **And many more** available on OpenRouter

## Migration Notes

### Removed Dependencies
The following dependencies are no longer required:
- `openai`
- `google-generativeai`
- `anthropic`

These can be removed from `pyproject.toml` if not used elsewhere.

### Environment Variables
API keys are now managed through `core/llm_adapter/config.yaml`:
- `OPENROUTER_API_KEY` - For OpenRouter access
- `GOOGLE_API_KEY` - For direct Gemini access
- `OPENAI_API_KEY` - For direct OpenAI access

### Removed Classes
The following provider classes were removed:
- `VisionProvider` (Protocol)
- `OpenAIVisionProvider`
- `GeminiVisionProvider`
- `ClaudeVisionProvider`
- `OpenRouterVisionProvider`

All functionality is now handled by the unified `MultimodalLLMClient` class.

## Testing

The refactored adapter maintains the same interface, so existing tests should continue to work. However, you may need to:

1. Configure test API keys in `core/llm_adapter/config.yaml`
2. Update mocks if tests were mocking provider-specific classes
3. Verify cost calculations match expected values

## Future Enhancements

With this refactoring, we can now:
1. Add `LoggingLLMAdapter` wrapper for vision calls
2. Implement usage tracking for multimodal calls
3. Add automatic fallback between vision providers
4. Centralize all LLM configuration in one place

## Related Files

- `app/services/multimodal_llm_adapter.py` - Refactored adapter
- `core/llm_adapter/config.yaml` - Configuration file
- `core/llm_adapter/llm_adapter/adapter.py` - Unified LLM adapter
- `app/services/logging_llm_adapter.py` - Logging wrapper (can be extended for vision)
