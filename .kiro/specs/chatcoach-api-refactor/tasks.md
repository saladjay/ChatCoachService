# Implementation Plan: ChatCoach API Refactor

## Overview

This implementation plan breaks down the ChatCoach API refactor into discrete, incremental tasks. Each task builds on previous work and includes testing to validate functionality early. The plan follows a bottom-up approach: configuration → services → API endpoints → integration → testing.

## Tasks

- [x] 1. Set up configuration and project structure
  - Create `app/api/v1/` directory structure
  - Create configuration models for screenshot processing
  - Add supported apps and languages to config
  - Set up logging configuration for submodules
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 1.1 Write unit tests for configuration loading

  - Test loading from config file
  - Test environment variable overrides
  - Test default values
  - _Requirements: 10.5_

- [x] 2. Implement Status Checker service
  - [x] 2.1 Create `app/services/status_checker.py`
    - Implement model availability checking
    - Check text detection, layout detection, text recognition models
    - Return aggregated health status
    - _Requirements: 2.1, 2.2, 2.5_

- [ ]* 2.2 Write unit tests for Status Checker
  - Test with all models available
  - Test with models unavailable
  - Test partial availability scenarios
  - _Requirements: 2.1, 2.2_

- [x] 3. Implement Screenshot Processor service
  - [x] 3.1 Create `app/services/screenshot_processor.py`
    - Import screenshotanalysis models
    - Implement lazy model loading
    - Implement image loading from URLs
    - _Requirements: 4.1, 4.2_

  - [x] 3.2 Implement text and layout detection
    - Call text detection analyzer
    - Call layout detection analyzer
    - Handle detection failures
    - _Requirements: 4.3, 4.4_

  - [x] 3.3 Implement text extraction and speaker identification
    - Extract text from detected boxes using OCR
    - Identify nickname from screenshot
    - Determine speaker (self vs other)
    - _Requirements: 4.5, 4.6, 4.7_

  - [x] 3.4 Implement coordinate normalization and message grouping
    - Normalize pixel coordinates to percentages (0.0-1.0)
    - Group consecutive messages by same speaker
    - Format as DialogItem models
    - _Requirements: 4.8, 4.9_

- [x] 3.5 Write property test for coordinate normalization

  - **Property 9: Coordinate Normalization Bounds**
  - **Validates: Requirements 4.8**

- [ ]* 3.6 Write property test for speaker identification
  - **Property 5: Speaker Identification Consistency**
  - **Validates: Requirements 4.6**

- [ ]* 3.7 Write property test for message grouping
  - **Property 6: Message Grouping Invariant**
  - **Validates: Requirements 4.9**

- [ ]* 3.8 Write unit tests for Screenshot Processor
  - Test with mock screenshotanalysis models
  - Test image loading failures
  - Test inference failures
  - Test edge cases (empty results, no nickname)
  - _Requirements: 4.10, 4.11, 4.12_

- [x] 4. Implement Metrics Collector service
  - [x] 4.1 Create `app/services/metrics_collector.py`
    - Implement request tracking
    - Track counts, latencies, error rates
    - Format as Prometheus text
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ]* 4.2 Write unit tests for Metrics Collector
  - Test metric recording
  - Test Prometheus format output
  - Test concurrent access
  - _Requirements: 5.1, 5.4_

- [x] 5. Implement API data models
  - [x] 5.1 Create `app/models/v1_api.py`
    - Define PredictRequest with validators
    - Define PredictResponse, ImageResult, DialogItem
    - Define HealthResponse, ErrorResponse
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [ ]* 5.2 Write property test for input validation
  - **Property 7: Input Validation**
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

- [ ]* 5.3 Write unit tests for request validation
  - Test app_name validation
  - Test language validation
  - Test conf_threshold boundaries
  - Test required fields
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 6. Implement Health endpoint
  - [x] 6.1 Create `app/api/v1/health.py`
    - Implement GET /health endpoint
    - Check model availability via StatusChecker
    - Return HealthResponse with status, timestamp, version
    - Return HTTP 401 if models unavailable
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ]* 6.2 Write property test for health response completeness
  - **Property 2: Health Check Response Completeness**
  - **Validates: Requirements 2.1**

- [ ]* 6.3 Write unit tests for Health endpoint
  - Test successful health check
  - Test model unavailable scenario
  - Test response structure
  - _Requirements: 2.1, 2.2, 2.4_

- [x] 7. Implement Predict endpoint
  - [x] 7.1 Create `app/api/v1/predict.py`
    - Implement POST /predict endpoint
    - Validate request parameters
    - Process each screenshot URL
    - Return structured results
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.10, 3.12_

  - [x] 7.2 Implement error handling
    - Handle model unavailable errors (HTTP 401)
    - Handle image load errors (HTTP 400)
    - Handle inference errors (HTTP 500)
    - Return descriptive error messages
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 7.3 Integrate with Orchestrator for reply generation
    - Check if reply parameter is true
    - Extract and format dialogs as conversation
    - Call Orchestrator with user_id, conversation, language
    - Include suggested_replies in response if successful
    - Handle Orchestrator failures gracefully
    - _Requirements: 3.8, 3.9, 3.11, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ]* 7.4 Write property test for screenshot analysis completeness
  - **Property 3: Screenshot Analysis Completeness**
  - **Validates: Requirements 3.1**

- [ ]* 7.5 Write property test for reply generation integration
  - **Property 4: Reply Generation Integration**
  - **Validates: Requirements 3.8, 9.4**

- [ ]* 7.6 Write property test for response format consistency
  - **Property 8: Response Format Consistency**
  - **Validates: Requirements 8.2, 8.5, 4.8**

- [ ]* 7.7 Write unit tests for Predict endpoint
  - Test with valid requests
  - Test with multiple URLs
  - Test with reply=true
  - Test with reply=false
  - Test error scenarios
  - _Requirements: 3.1, 3.8, 7.1, 7.2, 7.3, 7.4_

- [x] 8. Implement Metrics endpoint
  - [x] 8.1 Create `app/api/v1/chat_analysis.py`
    - Implement GET /metrics endpoint
    - Return Prometheus format metrics
    - Use PlainTextResponse
    - _Requirements: 5.1, 5.2, 5.3_

- [ ]* 8.2 Write unit tests for Metrics endpoint
  - Test Prometheus format output
  - Test metric values
  - _Requirements: 5.1, 5.3_

- [x] 9. Implement API router
  - [x] 9.1 Create `app/api/v1/router.py`
    - Create APIRouter with prefix "/api/v1/ChatCoach"
    - Include health, predict, chat_analysis routers
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 9.2 Update `app/main.py`
    - Import v1 router
    - Register v1 router with app
    - Configure OpenAPI docs URLs
    - _Requirements: 1.4, 1.5_

- [ ]* 9.3 Write property test for API endpoint structure
  - **Property 1: API Endpoint Structure**
  - **Validates: Requirements 1.1**

- [ ]* 9.4 Write integration tests for API router
  - Test all endpoints are accessible
  - Test OpenAPI docs generation
  - Test endpoint prefixes
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 10. Implement dependency injection
  - [x] 10.1 Create `app/core/v1_dependencies.py`
    - Create dependency for StatusChecker
    - Create dependency for ScreenshotProcessor
    - Create dependency for MetricsCollector
    - Initialize screenshotanalysis models
    - _Requirements: 4.1_

- [ ]* 10.2 Write unit tests for dependencies
  - Test dependency initialization
  - Test model loading
  - Test error handling
  - _Requirements: 4.1_

- [x] 11. Checkpoint - Integration testing
  - Ensure all endpoints are accessible
  - Test end-to-end screenshot analysis flow
  - Test reply generation integration
  - Verify error handling works correctly
  - Ask the user if questions arise

- [x] 12. Add logging and monitoring
  - [x] 12.1 Configure logging for v1 endpoints
    - Set up structured logging
    - Configure screenshotanalysis submodule logging
    - Add request/response logging
    - _Requirements: 10.3, 10.4_

  - [x] 12.2 Add metrics tracking to endpoints
    - Track request counts
    - Track response times
    - Track error rates
    - _Requirements: 5.4_

- [ ]* 12.3 Write integration tests for logging and metrics
  - Test log output format
  - Test metric collection
  - Test submodule logging configuration
  - _Requirements: 10.4, 5.4_

- [x] 13. Documentation and examples
  - [x] 13.1 Update API documentation
    - Document new endpoints
    - Add request/response examples
    - Document error codes
    - _Requirements: 1.4, 1.5_

  - [x] 13.2 Create example client code
    - Example for screenshot analysis
    - Example for reply generation
    - Example error handling
    - _Requirements: 3.1, 3.8_

- [x] 14. Final checkpoint - Comprehensive testing
  - Run all unit tests
  - Run all property tests
  - Run integration tests
  - Verify all requirements are met
  - Ask the user if questions arise

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Checkpoints ensure incremental validation
- The implementation follows a bottom-up approach: services → endpoints → integration
