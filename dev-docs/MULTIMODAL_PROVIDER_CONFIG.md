# Multimodal Provider Configuration

This document explains how to configure the multimodal (vision) LLM provider for screenshot analysis.

## Overview

The system uses multimodal LLMs to analyze chat screenshots. By default, it automatically selects the first available provider with a multimodal model configured. You can override this behavior using environment variables.

## Configuration Methods

### Method 1: Environment Variable (Recommended)

Set the `MULTIMODAL_DEFAULT_PROVIDER` environment variable to specify which provider to use for multimodal tasks.

**In `.env` file:**
```bash
MULTIMODAL_DEFAULT_PROVIDER=openrouter
```

**Or export in shell:**
```bash
export MULTIMODAL_DEFAULT_PROVIDER=openrouter
```

**Supported values:**
- `openrouter` - OpenRouter (supports multiple vision models)
- `gemini` - Google Gemini (supports SDK, HTTP, and Vertex AI modes)
- `dashscope` - Alibaba DashScope (Qwen-VL models)
- `openai` - OpenAI (GPT-4 Vision)

### Method 2: LLM Adapter Config (Not Recommended for Override)

The `core/llm_adapter/config.yaml` file defines available providers and their models. This file should contain the base configuration, not runtime overrides.

## How It Works

1. **Environment Variable Check**: On startup, the system checks for `MULTIMODAL_DEFAULT_PROVIDER`
2. **Validation**: Verifies the specified provider is configured with a multimodal model
3. **Fallback**: If the environment variable is not set or invalid, uses default selection logic
4. **Logging**: Logs which provider is being used for multimodal tasks

## Default Selection Logic (When No Override)

If `MULTIMODAL_DEFAULT_PROVIDER` is not set, the system selects providers in this order:

1. Default provider from `llm.default_provider` in config.yaml
2. `gemini`
3. `dashscope`
4. `openrouter`
5. `openai`

The first provider with:
- A configured `multimodal` model
- A valid API key (or Vertex AI credentials for Gemini)

## Examples

### Example 1: Use OpenRouter for Multimodal

```bash
# .env
MULTIMODAL_DEFAULT_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-xxxxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

### Example 2: Use Gemini Vertex AI for Multimodal

```bash
# .env
MULTIMODAL_DEFAULT_PROVIDER=gemini
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

```yaml
# core/llm_adapter/config.yaml
providers:
  gemini:
    mode: vertex
    project_id: your-gcp-project-id
    location: us-central1
    models:
      multimodal: gemini-1.5-flash-001
```

### Example 3: Use DashScope for Multimodal

```bash
# .env
MULTIMODAL_DEFAULT_PROVIDER=dashscope
```

```yaml
# core/llm_adapter/config.yaml
providers:
  dashscope:
    api_key: sk-xxxxx
    models:
      multimodal: qwen-vl-plus
```

## Verification

When the application starts, check the logs for:

```
INFO - Using multimodal provider from environment variable: openrouter (model: qwen/qwen3-vl-30b-a3b-instruct)
```

Or if using default selection:

```
INFO - Using multimodal provider: gemini (model: gemini-1.5-flash-001)
```

## Troubleshooting

### Provider Not Found

**Error:**
```
WARNING - Failed to use MULTIMODAL_DEFAULT_PROVIDER=gemini: Provider not configured: gemini
```

**Solution:** Ensure the provider is configured in `core/llm_adapter/config.yaml` with a multimodal model.

### No API Key

**Error:**
```
WARNING - Failed to use MULTIMODAL_DEFAULT_PROVIDER=openrouter: API key is empty
```

**Solution:** Set the required API key environment variable or configure it in config.yaml.

### No Multimodal Model

**Error:**
```
WARNING - Failed to use MULTIMODAL_DEFAULT_PROVIDER=openai: No multimodal model configured
```

**Solution:** Add a `multimodal` model to the provider's configuration:

```yaml
providers:
  openai:
    api_key: sk-xxxxx
    models:
      multimodal: gpt-4o  # Add this line
```

## Best Practices

1. **Use Environment Variables for Overrides**: Keep `config.yaml` as the base configuration, use `.env` for environment-specific overrides
2. **Test Before Production**: Verify the provider works with a test screenshot before deploying
3. **Monitor Costs**: Different providers have different pricing for vision models
4. **Check Quotas**: Ensure your provider has sufficient quota for your expected load
5. **Have a Fallback**: Configure multiple providers in case one fails or hits quota limits

## Provider Comparison

| Provider | Pros | Cons | Best For |
|----------|------|------|----------|
| OpenRouter | Multiple models, unified API | Requires API key | Flexibility, testing |
| Gemini Vertex AI | High quota, regional deployment | Complex setup | Production, high volume |
| Gemini SDK | Easy setup, official SDK | Lower quota | Development, testing |
| DashScope | Good for Chinese content | China-focused | Chinese language apps |
| OpenAI | High quality, reliable | Expensive | High-quality requirements |

## Related Documentation

- [Gemini Modes](../core/llm_adapter/GEMINI_MODES.md) - Detailed Gemini configuration
- [LLM Adapter Config](../core/llm_adapter/config.example.yaml) - Configuration examples
- [Vertex AI Setup](../core/llm_adapter/check_vertex_env.py) - Environment check script
