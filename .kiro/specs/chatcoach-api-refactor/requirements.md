# Requirements Document

## Introduction

This document specifies the requirements for refactoring the ChatCoach API to align with the old-api service structure. The old-api service provides a unified interface for chat screenshot analysis and reply generation, which we will adapt to the current ChatCoach architecture while maintaining compatibility with the screenshotanalysis library.

## Glossary

- **ChatCoach**: The current service that generates conversation reply suggestions
- **Old_API**: The legacy service that provides chat screenshot analysis and reply generation
- **Screenshot_Parser**: Service component that analyzes chat screenshots using the screenshotanalysis library
- **Orchestrator**: Service component that coordinates reply generation workflow
- **API_Router**: FastAPI router that defines endpoint structure and routing
- **Dialog_Item**: A structured representation of a single chat message with position, text, and speaker information
- **Screenshotanalysis**: External library (installed in core/) that provides OCR and layout detection for chat screenshots

## Requirements

### Requirement 1: API Structure Alignment

**User Story:** As a developer, I want the ChatCoach API to follow the old-api structure, so that the service has a consistent and familiar interface pattern.

#### Acceptance Criteria

1. THE API_Router SHALL use the prefix "/api/v1/ChatCoach" for all endpoints
2. THE API_Router SHALL organize endpoints into logical groups (health, predict, chat_analysis)
3. THE API_Router SHALL maintain versioning through the URL path structure
4. THE API_Router SHALL provide OpenAPI documentation at "/api/v1/ChatCoach/docs"
5. THE API_Router SHALL provide ReDoc documentation at "/api/v1/ChatCoach/redoc"

### Requirement 2: Health Check Endpoint

**User Story:** As a system administrator, I want a health check endpoint, so that I can monitor service availability and model status.

#### Acceptance Criteria

1. WHEN a health check request is received, THE Health_Endpoint SHALL return service status, timestamp, and version
2. IF the screenshotanalysis models are unavailable, THEN THE Health_Endpoint SHALL return HTTP 401 with "Model Unavailable" message
3. THE Health_Endpoint SHALL be accessible at "/api/v1/ChatCoach/health"
4. THE Health_Endpoint SHALL return a HealthResponse model with status, timestamp, and version fields
5. THE Health_Endpoint SHALL check the availability of text detection, layout detection, and text recognition models

### Requirement 3: Predict Endpoint for Screenshot Analysis

**User Story:** As a client application, I want to submit chat screenshots for analysis, so that I can extract structured conversation data.

#### Acceptance Criteria

1. WHEN a predict request is received with image URLs, THE Predict_Endpoint SHALL analyze each screenshot and return structured dialog data
2. THE Predict_Endpoint SHALL accept a list of image URLs (minimum 1 URL required)
3. THE Predict_Endpoint SHALL accept app_name parameter to specify the chat application type
4. THE Predict_Endpoint SHALL accept language parameter to specify the conversation language
5. THE Predict_Endpoint SHALL accept user_id parameter for user identification
6. THE Predict_Endpoint SHALL accept optional request_id parameter for request tracking
7. THE Predict_Endpoint SHALL accept optional conf_threshold parameter for detection confidence (0.0-1.0)
8. THE Predict_Endpoint SHALL accept optional reply parameter (boolean) to request suggested replies
9. WHEN reply parameter is true, THEN THE Predict_Endpoint SHALL call the Orchestrator to generate suggested replies
10. THE Predict_Endpoint SHALL return results containing URL, dialogs with position, text, speaker, and from_user fields
11. IF reply is requested, THEN THE Predict_Endpoint SHALL include suggested_replies in the response
12. THE Predict_Endpoint SHALL be accessible at "/api/v1/ChatCoach/predict"

### Requirement 4: Screenshot Processing Integration

**User Story:** As a developer, I want to integrate the screenshotanalysis library, so that the service can perform OCR and layout detection on chat screenshots.

#### Acceptance Criteria

1. THE Screenshot_Parser SHALL import text detection, layout detection, and text recognition models from screenshotanalysis
2. THE Screenshot_Parser SHALL load images from URLs or base64 data
3. THE Screenshot_Parser SHALL perform text detection analysis on screenshots
4. THE Screenshot_Parser SHALL perform layout detection analysis on screenshots
5. THE Screenshot_Parser SHALL extract text from detected text boxes using the text recognition model
6. THE Screenshot_Parser SHALL identify chat message speakers (self vs other)
7. THE Screenshot_Parser SHALL extract nickname information from screenshots
8. THE Screenshot_Parser SHALL return normalized position coordinates as percentages (0.0-1.0)
9. THE Screenshot_Parser SHALL group consecutive messages by the same speaker
10. IF model loading fails, THEN THE Screenshot_Parser SHALL raise a model unavailable error
11. IF image loading fails, THEN THE Screenshot_Parser SHALL raise an image load error
12. IF inference fails, THEN THE Screenshot_Parser SHALL raise an inference error

### Requirement 5: Metrics Endpoint

**User Story:** As a system administrator, I want to collect performance metrics, so that I can monitor service performance and resource usage.

#### Acceptance Criteria

1. THE Metrics_Endpoint SHALL return Prometheus-compatible metrics
2. THE Metrics_Endpoint SHALL be accessible at "/api/v1/ChatCoach/metrics"
3. THE Metrics_Endpoint SHALL return metrics in plain text format
4. THE Metrics_Endpoint SHALL track request counts, latencies, and error rates

### Requirement 6: Request Validation

**User Story:** As a developer, I want comprehensive request validation, so that invalid requests are rejected with clear error messages.

#### Acceptance Criteria

1. WHEN app_name is provided, THE API SHALL validate it against a list of supported chat applications
2. WHEN language is provided, THE API SHALL validate it against a list of supported languages
3. WHEN conf_threshold is provided, THE API SHALL validate it is between 0.0 and 1.0
4. WHEN urls list is empty, THE API SHALL reject the request with a validation error
5. WHEN user_id is empty, THE API SHALL reject the request with a validation error
6. THE API SHALL return descriptive error messages for validation failures

### Requirement 7: Error Handling

**User Story:** As a client application, I want consistent error responses, so that I can handle errors appropriately.

#### Acceptance Criteria

1. WHEN a model is unavailable, THE API SHALL return HTTP 401 with "Model Unavailable" error
2. WHEN image loading fails, THE API SHALL return HTTP 400 with "Load Image Failed" error
3. WHEN inference fails, THE API SHALL return HTTP 500 with "Inference Error" error
4. WHEN validation fails, THE API SHALL return HTTP 400 with validation error details
5. THE API SHALL log all errors with appropriate severity levels

### Requirement 8: Response Format Compatibility

**User Story:** As a client application, I want response formats compatible with the old-api, so that I can migrate with minimal changes.

#### Acceptance Criteria

1. THE Predict_Endpoint SHALL return a PredictResponse with success, message, user_id, request_id, and results fields
2. THE Dialog_Item SHALL include position as [min_x, min_y, max_x, max_y] in percentage coordinates
3. THE Dialog_Item SHALL include text field with the message content
4. THE Dialog_Item SHALL include speaker field identifying the message sender
5. THE Dialog_Item SHALL include from_user boolean field indicating if the message is from the user
6. THE ImageResult SHALL include url field with the original image URL
7. THE ImageResult SHALL include dialogs array with all extracted messages

### Requirement 9: Orchestrator Integration

**User Story:** As a developer, I want the predict endpoint to integrate with the existing Orchestrator, so that suggested replies can be generated when requested.

#### Acceptance Criteria

1. WHEN reply parameter is true, THE Predict_Endpoint SHALL extract all dialogs from screenshot results
2. WHEN reply parameter is true, THE Predict_Endpoint SHALL format dialogs as conversation history
3. WHEN reply parameter is true, THE Predict_Endpoint SHALL call the Orchestrator with user_id, conversation, and language
4. WHEN the Orchestrator returns successfully, THE Predict_Endpoint SHALL include suggested_replies in the response
5. WHEN the Orchestrator fails, THE Predict_Endpoint SHALL return results without suggested_replies

### Requirement 10: Configuration Management

**User Story:** As a system administrator, I want configurable service parameters, so that I can adjust behavior without code changes.

#### Acceptance Criteria

1. THE Service SHALL load supported app_names from configuration
2. THE Service SHALL load supported languages from configuration
3. THE Service SHALL load logging configuration including level and format
4. THE Service SHALL configure submodule loggers (screenshotanalysis) to use service logging settings
5. THE Service SHALL support environment-based configuration overrides
