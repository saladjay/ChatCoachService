# Multimodal Image Transport Format Configuration

## Overview

The `LLM_MULTIMODAL_IMAGE_FORMAT` environment variable controls how images are sent to multimodal LLM providers for vision tasks (screenshot parsing, merge_step analysis, etc.).

## Configuration

Add to your `.env` file:

```bash
# Multimodal image transport format
# Options: "base64" or "url"
LLM_MULTIMODAL_IMAGE_FORMAT=base64
```

## Options

### base64 (Recommended - Default)

**How it works:**
1. Downloads the image from URL
2. Compresses the image to max 800px (if needed)
3. Encodes as base64 string
4. Sends base64 data to LLM provider

**Pros:**
- ✅ Works with all providers (OpenRouter, DashScope, Gemini, OpenAI)
- ✅ Ensures consistent image processing
- ✅ Image metadata (width/height) matches what LLM sees
- ✅ No external URL access required by LLM provider
- ✅ Reduces token usage and cost (compressed images)

**Cons:**
- ❌ Slightly slower (download + compress + encode time)
- ❌ Larger payload size than URL

**Use when:**
- Using DashScope with internal network URLs (required)
- Need guaranteed compatibility
- Image URLs are not publicly accessible
- Want to reduce LLM token usage (compressed images use fewer tokens)
- Default choice for production

### url

**How it works:**
1. Validates the image URL
2. Sends the URL directly to LLM provider
3. Provider downloads the original image themselves
4. **No compression** - provider processes the full-resolution image

**Pros:**
- ✅ Faster (no download/compress/encode time)
- ✅ Smaller payload size
- ✅ Less bandwidth usage from your server
- ✅ Provider processes original high-resolution image

**Cons:**
- ❌ Requires image URL to be publicly accessible from internet
- ❌ DashScope cannot access localhost or internal network URLs (192.168.x.x, 10.x.x.x)
- ❌ Provider may process image differently than expected
- ❌ Higher token usage (full-resolution images use more tokens)
- ❌ Higher LLM cost due to more tokens

**Use when:**
- Using OpenRouter or OpenAI (they support URL format)
- Images are publicly accessible on the internet
- Speed is critical
- You need the LLM to see the full-resolution image
- You've verified your provider supports URL format

## Provider Compatibility

| Provider | base64 | url | Notes |
|----------|--------|-----|-------|
| OpenRouter | ✅ | ✅ | Both formats fully supported |
| OpenAI | ✅ | ✅ | Both formats fully supported |
| Gemini | ✅ | ✅ | Both formats fully supported |
| DashScope | ✅ | ✅ | Both formats supported, URL must be publicly accessible |

**Note:** While DashScope supports URL format, the URL must be publicly accessible from the internet. If you encounter "The provided URL does not appear to be valid" error, it may mean:
1. The URL is not publicly accessible (e.g., localhost, internal network)
2. The URL requires authentication
3. The image format is not supported

In such cases, use base64 format instead.

## Example Configuration

### For DashScope (Required)
```bash
LLM_MULTIMODAL_IMAGE_FORMAT=base64
```

### For OpenRouter (Faster)
```bash
LLM_MULTIMODAL_IMAGE_FORMAT=url
```

## Implementation Details

The configuration is used in:
- `app/services/screenshot_parser.py` - Screenshot parsing
- `app/services/orchestrator.py` - Merge step analysis (uses base64 by default)

The setting is defined in:
- `app/core/config.py` - `LLMConfig.multimodal_image_format`

## Troubleshooting

### Error: "The provided URL does not appear to be valid"

This error from DashScope usually means:
1. **URL is not publicly accessible** - DashScope cannot access localhost (127.0.0.1) or internal network URLs (192.168.x.x, 10.x.x.x)
2. **URL requires authentication** - The image URL needs login or API key
3. **Network restrictions** - Firewall or network policy blocks DashScope's access

**Solutions:**
1. Use base64 format (recommended):
   ```bash
   LLM_MULTIMODAL_IMAGE_FORMAT=base64
   ```

2. Make sure the image URL is publicly accessible from the internet

3. Use a public image hosting service (e.g., Alibaba OSS, AWS S3 with public access)

### Images not processing correctly

If the LLM seems to see a different image than expected, use base64 format to ensure consistent processing:
```bash
LLM_MULTIMODAL_IMAGE_FORMAT=base64
```
