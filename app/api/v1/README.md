# ChatCoach API v1

This directory contains the v1 API implementation for ChatCoach, providing screenshot analysis and reply generation capabilities.

## Structure

```
app/api/v1/
├── __init__.py          # Package initialization
├── router.py            # Main API router with /api/v1/ChatCoach prefix
├── health.py            # Health check endpoint
├── predict.py           # Screenshot analysis and prediction endpoint
├── chat_analysis.py     # Metrics endpoint
└── README.md            # This file
```

## Configuration

The v1 API uses configuration from `config.yaml` and environment variables. See `app/core/v1_config.py` for details.

### Supported Apps

The API supports the following chat applications:
- WhatsApp
- Telegram
- Discord
- WeChat
- LINE
- Instagram

### Supported Languages

The API supports the following languages:
- English (en)
- Chinese (zh)
- Spanish (es)
- Arabic (ar)
- Portuguese (pt)
- French (fr)
- German (de)
- Japanese (ja)
- Korean (ko)

### Environment Variables

Configuration can be overridden using environment variables with the `V1_` prefix:

- `V1_SCREENSHOT__SUPPORTED_APPS`: Comma-separated list of supported apps
- `V1_SCREENSHOT__SUPPORTED_LANGUAGES`: Comma-separated list of supported languages
- `V1_SCREENSHOT__DEFAULT_CONF_THRESHOLD`: Default confidence threshold (0.0-1.0)
- `V1_LOGGING__LEVEL`: Main logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `V1_LOGGING__SUBMODULE_LEVEL`: Submodule logging level

## Endpoints

### Health Check
- **Path**: `/api/v1/ChatCoach/health`
- **Method**: GET
- **Description**: Check service health and model availability

### Predict
- **Path**: `/api/v1/ChatCoach/predict`
- **Method**: POST
- **Description**: Analyze chat screenshots and optionally generate reply suggestions

### Metrics
- **Path**: `/api/v1/ChatCoach/metrics`
- **Method**: GET
- **Description**: Get Prometheus-compatible performance metrics

## Logging

The v1 API configures logging for both the main application and submodules (screenshotanalysis, paddleocr). By default:
- Main application logs at INFO level
- Submodules log at WARNING level to reduce noise

This can be customized in `config.yaml` or via environment variables.
