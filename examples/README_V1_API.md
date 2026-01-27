# ChatCoach API v1 Examples

This directory contains example client code for the ChatCoach API v1. These examples demonstrate how to use the API for screenshot analysis, reply generation, and error handling.

## Prerequisites

Install the required dependencies:

```bash
pip install httpx
```

## Examples

### 1. Screenshot Analysis Example

**File**: `v1_screenshot_analysis_example.py`

Demonstrates how to analyze chat screenshots and extract structured conversation data.

**Basic Usage**:
```bash
python examples/v1_screenshot_analysis_example.py
```

**With Custom Configuration**:
```bash
python examples/v1_screenshot_analysis_example.py \
  --server http://localhost:8000 \
  --app whatsapp \
  --language en \
  --user-id user123
```

**Analyze Multiple Screenshots**:
```bash
python examples/v1_screenshot_analysis_example.py \
  --urls https://example.com/screenshot1.jpg https://example.com/screenshot2.jpg \
  --app telegram \
  --language zh
```

**With Confidence Threshold**:
```bash
python examples/v1_screenshot_analysis_example.py \
  --urls https://example.com/screenshot.jpg \
  --conf-threshold 0.7 \
  --output results.json
```

**Available Options**:
- `--server`: API server URL (default: http://localhost:8000)
- `--urls`: Image URLs to analyze (space-separated)
- `--app`: Chat application type (whatsapp, telegram, discord, etc.)
- `--language`: Conversation language (en, zh, es, etc.)
- `--user-id`: User identifier
- `--request-id`: Optional request tracking ID
- `--conf-threshold`: Detection confidence threshold (0.0-1.0)
- `--output`: Save results to JSON file
- `--skip-health-check`: Skip health check before analysis

---

### 2. Reply Generation Example

**File**: `v1_reply_generation_example.py`

Demonstrates how to analyze screenshots and generate intelligent reply suggestions.

**Basic Usage**:
```bash
python examples/v1_reply_generation_example.py
```

**With Custom Configuration**:
```bash
python examples/v1_reply_generation_example.py \
  --server http://localhost:8000 \
  --app telegram \
  --language zh \
  --user-id user123
```

**With Conversation Summary**:
```bash
python examples/v1_reply_generation_example.py \
  --urls https://example.com/screenshot.jpg \
  --show-summary \
  --output results_with_replies.json
```

**Available Options**:
- `--server`: API server URL (default: http://localhost:8000)
- `--urls`: Image URLs to analyze (space-separated)
- `--app`: Chat application type
- `--language`: Conversation language
- `--user-id`: User identifier
- `--request-id`: Optional request tracking ID
- `--conf-threshold`: Detection confidence threshold (0.0-1.0)
- `--output`: Save results to JSON file
- `--skip-health-check`: Skip health check before analysis
- `--show-summary`: Show conversation summary

**Note**: Reply generation adds 1-3 seconds to response time as it calls the Orchestrator service.

---

### 3. Error Handling Example

**File**: `v1_error_handling_example.py`

Demonstrates comprehensive error handling for various error scenarios.

**Test All Error Scenarios**:
```bash
python examples/v1_error_handling_example.py
```

**Test Specific Scenario**:
```bash
python examples/v1_error_handling_example.py --scenario invalid_app_name
```

**Available Scenarios**:
- `model_unavailable`: Test model unavailable error (401)
- `invalid_app_name`: Test invalid app name validation (400)
- `invalid_language`: Test invalid language validation (400)
- `invalid_conf_threshold`: Test invalid confidence threshold (422)
- `empty_urls`: Test empty URLs list validation (422)
- `empty_user_id`: Test empty user ID validation (422)
- `invalid_image_url`: Test invalid image URL (400)
- `network_error`: Test network connection error
- `all`: Test all scenarios (default)

**Available Options**:
- `--server`: API server URL (default: http://localhost:8000)
- `--scenario`: Specific error scenario to test

---

## Common Error Scenarios

### 1. Model Unavailable (401)

**Cause**: Screenshotanalysis models are not loaded or failed to initialize.

**Solution**:
- Check server logs for model loading errors
- Ensure screenshotanalysis library is installed
- Restart the service

### 2. Invalid App Name (400)

**Cause**: The `app_name` parameter is not in the list of supported applications.

**Solution**:
- Use a supported app name: whatsapp, telegram, discord, etc.
- Check `config.yaml` for the full list of supported apps

### 3. Invalid Language (400)

**Cause**: The `language` parameter is not in the list of supported languages.

**Solution**:
- Use a supported language code: en, zh, es, etc.
- Check `config.yaml` for the full list of supported languages

### 4. Invalid Confidence Threshold (422)

**Cause**: The `conf_threshold` parameter is outside the valid range [0.0, 1.0].

**Solution**:
- Use a value between 0.0 and 1.0
- Lower values = more detections (more false positives)
- Higher values = fewer detections (fewer false positives)

### 5. Image Load Failed (400)

**Cause**: Failed to download or process the image from the provided URL.

**Solution**:
- Verify the image URL is accessible
- Check network connectivity
- Ensure the URL points to a valid image file

### 6. Inference Error (500)

**Cause**: Screenshot analysis failed during model inference.

**Solution**:
- Check image format and quality
- Review server logs for details
- Try with a different image

---

## Best Practices

### 1. Error Handling

Always implement proper error handling:

```python
try:
    results = await client.analyze_screenshots(...)
    if not results.get("success"):
        print(f"Request failed: {results.get('message')}")
        # Handle failure
    else:
        # Process results
        pass
except httpx.HTTPStatusError as e:
    print(f"HTTP Error: {e.response.status_code}")
    # Handle HTTP errors
except httpx.HTTPError as e:
    print(f"Network Error: {e}")
    # Handle network errors
```

### 2. Health Checks

Check API health before making requests:

```python
health = await client.check_health()
if health['status'] != 'healthy':
    print("API is not healthy")
    # Handle unhealthy state
```

### 3. Request Tracking

Use `request_id` for debugging and support:

```python
import uuid

request_id = str(uuid.uuid4())
results = await client.analyze_screenshots(
    ...,
    request_id=request_id,
)
print(f"Request ID: {request_id}")
```

### 4. Batch Processing

Process multiple screenshots efficiently:

```python
# Good: Process multiple screenshots in one request
results = await client.analyze_screenshots(
    urls=[url1, url2, url3],
    ...
)

# Avoid: Making separate requests for each screenshot
# (unless you need to handle them independently)
```

### 5. Timeout Configuration

Adjust timeouts based on your needs:

```python
# For screenshot analysis only
timeout = 120.0  # 2 minutes

# For reply generation
timeout = 180.0  # 3 minutes (includes Orchestrator call)
```

---

## Response Format

### Screenshot Analysis Response

```json
{
  "success": true,
  "message": "Screenshot analysis completed successfully",
  "user_id": "user123",
  "request_id": "req-456",
  "results": [
    {
      "url": "https://example.com/screenshot.jpg",
      "dialogs": [
        {
          "position": [0.1, 0.2, 0.9, 0.3],
          "text": "Hey, how are you?",
          "speaker": "John",
          "from_user": false
        }
      ]
    }
  ]
}
```

### Reply Generation Response

```json
{
  "success": true,
  "message": "Screenshot analysis completed successfully",
  "user_id": "user123",
  "request_id": "req-456",
  "results": [...],
  "suggested_replies": [
    "That's wonderful to hear!",
    "Glad you're doing well!",
    "Great! What have you been up to?"
  ]
}
```

---

## Troubleshooting

### Server Not Running

**Error**: `Connection Error: Cannot connect to http://localhost:8000`

**Solution**:
```bash
# Start the server
python main.py

# Or use the startup script
./start_server.sh  # Linux/Mac
start_server.ps1   # Windows
```

### Models Not Loaded

**Error**: `Model Unavailable`

**Solution**:
1. Check if screenshotanalysis is installed:
   ```bash
   pip list | grep screenshotanalysis
   ```

2. Check server logs for model loading errors

3. Restart the server

### Invalid Configuration

**Error**: `Validation error: app_name must be one of: ...`

**Solution**:
Check `config.yaml` for supported values:
```yaml
v1_api:
  supported_languages:
    - en
    - zh
    - es
```

---

## Related Documentation

- [API Documentation](../docs/api/v1-chatcoach-api.md)
- [Quick Start Guide](../docs/setup/QUICK_START_SERVER.md)
- [Configuration Setup](../docs/task-summaries/task-1-configuration-setup.md)
- [Integration Testing](../docs/task-summaries/task-11-integration-testing.md)

---

## Support

For issues or questions:
1. Check the [API Documentation](../docs/api/v1-chatcoach-api.md)
2. Review server logs for detailed error information
3. Use `request_id` when reporting issues
4. Contact the development team with error details

---

## License

See the main project LICENSE file for details.
