# ChatCoach API v1 Documentation

## Overview

The ChatCoach API v1 provides endpoints for analyzing chat screenshots and generating reply suggestions. The API uses the screenshotanalysis library to extract structured conversation data from images and integrates with the Orchestrator service for intelligent reply generation.

**Base URL**: `/api/v1/ChatCoach`

**API Documentation**:
- Swagger UI: `/api/v1/ChatCoach/docs`
- ReDoc: `/api/v1/ChatCoach/redoc`

## Authentication

Currently, the API does not require authentication. Future versions may implement API key or OAuth authentication.

## Endpoints

### 1. Health Check

Check the service health and model availability.

**Endpoint**: `GET /api/v1/ChatCoach/health`

**Response**: `200 OK`

```json
{
  "status": "healthy",
  "timestamp": "2026-01-26T10:30:00Z",
  "version": "1.0.0",
  "models": {
    "text_detection": true,
    "layout_detection": true,
    "text_recognition": true
  }
}
```

**Error Response**: `401 Unauthorized` (when models are unavailable)

```json
{
  "detail": "Model Unavailable"
}
```

**Example Request**:

```bash
curl -X GET "http://localhost:8000/api/v1/ChatCoach/health"
```

---

### 2. Predict (Screenshot Analysis)

Analyze chat screenshots to extract structured conversation data and optionally generate reply suggestions.

**Endpoint**: `POST /api/v1/ChatCoach/predict`

**Request Body**:

```json
{
  "urls": ["https://example.com/screenshot1.jpg"],
  "app_name": "whatsapp",
  "language": "en",
  "user_id": "user123",
  "request_id": "req-456",
  "conf_threshold": 0.5,
  "reply": true
}
```

**Request Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `urls` | `array[string]` | Yes | List of image URLs to analyze (minimum 1) |
| `app_name` | `string` | Yes | Chat application type (e.g., "whatsapp", "telegram", "discord") |
| `language` | `string` | Yes | Conversation language (e.g., "en", "zh", "es") |
| `user_id` | `string` | Yes | User identifier (minimum 1 character) |
| `request_id` | `string` | No | Optional request tracking ID |
| `conf_threshold` | `float` | No | Detection confidence threshold (0.0-1.0, default: 0.5) |
| `reply` | `boolean` | No | Whether to generate reply suggestions (default: false) |

**Response**: `200 OK`

```json
{
  "success": true,
  "message": "Screenshot analysis completed successfully",
  "user_id": "user123",
  "request_id": "req-456",
  "results": [
    {
      "url": "https://example.com/screenshot1.jpg",
      "dialogs": [
        {
          "position": [0.1, 0.2, 0.9, 0.3],
          "text": "Hey, how are you?",
          "speaker": "John",
          "from_user": false
        },
        {
          "position": [0.1, 0.35, 0.9, 0.45],
          "text": "I'm doing great, thanks!",
          "speaker": "self",
          "from_user": true
        }
      ]
    }
  ],
  "suggested_replies": [
    "That's wonderful to hear!",
    "Glad you're doing well!",
    "Great! What have you been up to?"
  ]
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `success` | `boolean` | Whether the request was successful |
| `message` | `string` | Status message |
| `user_id` | `string` | User identifier from request |
| `request_id` | `string` | Request tracking ID (if provided) |
| `results` | `array[ImageResult]` | Analysis results for each image |
| `suggested_replies` | `array[string]` | Reply suggestions (only if `reply=true`) |

**ImageResult Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `url` | `string` | Original image URL |
| `dialogs` | `array[DialogItem]` | Extracted conversation messages |

**DialogItem Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `position` | `array[float]` | Bounding box [min_x, min_y, max_x, max_y] in percentage (0.0-1.0) |
| `text` | `string` | Message text content |
| `speaker` | `string` | Speaker identifier ("self" for user, or speaker name) |
| `from_user` | `boolean` | Whether the message is from the user |

**Example Request**:

```bash
curl -X POST "http://localhost:8000/api/v1/ChatCoach/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/screenshot.jpg"],
    "app_name": "whatsapp",
    "language": "en",
    "user_id": "user123",
    "reply": true
  }'
```

---

### 3. Metrics

Get Prometheus-compatible performance metrics.

**Endpoint**: `GET /api/v1/ChatCoach/metrics`

**Response**: `200 OK` (Plain text, Prometheus format)

```
# HELP chatcoach_requests_total Total number of requests
# TYPE chatcoach_requests_total counter
chatcoach_requests_total{endpoint="/predict",status="200"} 42
chatcoach_requests_total{endpoint="/health",status="200"} 15

# HELP chatcoach_request_duration_seconds Request duration in seconds
# TYPE chatcoach_request_duration_seconds histogram
chatcoach_request_duration_seconds_bucket{endpoint="/predict",le="0.5"} 30
chatcoach_request_duration_seconds_bucket{endpoint="/predict",le="1.0"} 40
chatcoach_request_duration_seconds_bucket{endpoint="/predict",le="+Inf"} 42
chatcoach_request_duration_seconds_sum{endpoint="/predict"} 25.5
chatcoach_request_duration_seconds_count{endpoint="/predict"} 42
```

**Example Request**:

```bash
curl -X GET "http://localhost:8000/api/v1/ChatCoach/metrics"
```

---

## Error Codes

The API uses standard HTTP status codes to indicate success or failure:

### Success Codes

| Code | Description |
|------|-------------|
| `200 OK` | Request successful |

### Client Error Codes

| Code | Description | Example |
|------|-------------|---------|
| `400 Bad Request` | Invalid request parameters or image load failure | Invalid `app_name`, empty `urls` list, image download failed |
| `401 Unauthorized` | Models unavailable | Screenshotanalysis models not loaded |
| `422 Unprocessable Entity` | Validation error | `conf_threshold` outside [0.0, 1.0] range |

### Server Error Codes

| Code | Description | Example |
|------|-------------|---------|
| `500 Internal Server Error` | Inference or processing error | Screenshot analysis failed, unexpected exception |

### Error Response Format

All errors return a JSON response with error details:

```json
{
  "detail": "Error description"
}
```

Or for predict endpoint failures:

```json
{
  "success": false,
  "message": "Error description",
  "user_id": "user123",
  "request_id": "req-456",
  "results": []
}
```

### Common Error Scenarios

#### 1. Model Unavailable (401)

**Cause**: Screenshotanalysis models are not loaded or failed to initialize.

**Response**:
```json
{
  "detail": "Model Unavailable"
}
```

**Solution**: Check server logs, ensure screenshotanalysis library is installed, restart the service.

#### 2. Invalid App Name (400)

**Cause**: The `app_name` parameter is not in the list of supported applications.

**Response**:
```json
{
  "detail": "Validation error: app_name must be one of: whatsapp, telegram, discord"
}
```

**Solution**: Use a supported app name from the configuration.

#### 3. Invalid Language (400)

**Cause**: The `language` parameter is not in the list of supported languages.

**Response**:
```json
{
  "detail": "Validation error: language must be one of: en, zh, es"
}
```

**Solution**: Use a supported language code from the configuration.

#### 4. Invalid Confidence Threshold (422)

**Cause**: The `conf_threshold` parameter is outside the valid range [0.0, 1.0].

**Response**:
```json
{
  "detail": [
    {
      "loc": ["body", "conf_threshold"],
      "msg": "ensure this value is greater than or equal to 0.0",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

**Solution**: Provide a value between 0.0 and 1.0.

#### 5. Image Load Failed (400)

**Cause**: Failed to download or process the image from the provided URL.

**Response**:
```json
{
  "success": false,
  "message": "Load image failed: Connection timeout",
  "user_id": "user123",
  "results": []
}
```

**Solution**: Verify the image URL is accessible, check network connectivity.

#### 6. Inference Error (500)

**Cause**: Screenshot analysis failed during model inference.

**Response**:
```json
{
  "success": false,
  "message": "Inference error: Model prediction failed",
  "user_id": "user123",
  "results": []
}
```

**Solution**: Check image format and quality, review server logs for details.

---

## Configuration

The API behavior can be configured through `config.yaml`:

```yaml
v1_api:
  supported_languages:
    - en
    - zh
    - es
    - fr
  
  screenshot:
    default_conf_threshold: 0.5
    model_load_timeout: 30.0
    history_update_interval: 10
  
  logging:
    level: INFO
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    submodule_level: WARNING
```

### Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `supported_languages` | List of supported languages | `["en", "zh"]` |
| `default_conf_threshold` | Default detection confidence threshold | `0.5` |
| `model_load_timeout` | Model loading timeout in seconds | `30.0` |
| `history_update_interval` | History update frequency | `10` |
| `logging.level` | Logging level | `INFO` |
| `logging.submodule_level` | Submodule logging level | `WARNING` |

---

## Rate Limiting

Currently, the API does not implement rate limiting. Future versions may add rate limiting based on:
- Requests per minute per user
- Concurrent requests per user
- Total requests per day

---

## Best Practices

### 1. Image URLs

- Use HTTPS URLs for security
- Ensure images are publicly accessible or use signed URLs
- Recommended image formats: JPEG, PNG
- Recommended resolution: 720p or higher for better OCR accuracy

### 2. Batch Processing

- Process multiple screenshots in a single request using the `urls` array
- Maximum recommended batch size: 5 images per request
- For larger batches, split into multiple requests

### 3. Error Handling

- Always check the `success` field in responses
- Implement retry logic for transient errors (500 errors)
- Log `request_id` for debugging and support

### 4. Reply Generation

- Only request replies (`reply=true`) when needed to reduce latency
- Reply generation adds 1-3 seconds to response time
- Replies are generated based on conversation context and user profile

### 5. Performance Optimization

- Cache results when processing the same screenshot multiple times
- Use appropriate `conf_threshold` values (lower = more detections, higher = fewer false positives)
- Monitor metrics endpoint for performance insights

---

## Changelog

### Version 1.0.0 (2026-01-26)

- Initial release of ChatCoach API v1
- Screenshot analysis with screenshotanalysis library integration
- Reply generation with Orchestrator integration
- Health check and metrics endpoints
- Support for multiple chat applications and languages
- Configurable detection confidence threshold
- Comprehensive error handling and validation

---

## Support

For issues, questions, or feature requests:
- Check the API documentation at `/api/v1/ChatCoach/docs`
- Review server logs for detailed error information
- Contact the development team with `request_id` for support

---

## Related Documentation

- [Quick Start Guide](../setup/QUICK_START_SERVER.md)
- [Configuration Setup](../task-summaries/task-1-configuration-setup.md)
- [Integration Testing](../task-summaries/task-11-integration-testing.md)
- [Logging and Monitoring](../task-summaries/task-12-logging-monitoring.md)
