# Implementation Plan: Chat Screenshot Parser

## Overview

This implementation plan breaks down the chat screenshot parser feature into discrete, incremental tasks. The approach follows a bottom-up strategy: building core components first, then integrating them, and finally adding the API layer. Each task builds on previous work, ensuring no orphaned code.

## Tasks

- [x] 1. Set up project structure and data models
  - Create directory structure for new modules
  - Define Pydantic models for requests, responses, and internal data structures
  - Add dependencies to pyproject.toml (httpx, Pillow, openai/anthropic/google-generativeai SDKs)
  - _Requirements: 1.4, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10_

- [x] 2. Implement Image Fetcher component
  - [x] 2.1 Create ImageFetcher class with URL validation
    - Implement URL format validation (HTTP/HTTPS only)
    - Add URL accessibility check
    - _Requirements: 5.1_

  - [x] 2.2 Write property test for URL validation

    - **Property 14: URL Format Validation**
    - **Validates: Requirements 5.1**

  - [x] 2.3 Implement image download functionality
    - Use httpx for async HTTP requests
    - Handle download errors and timeouts
    - _Requirements: 5.2_

  - [x] 2.4 Implement dimension extraction
    - Use Pillow to extract width and height
    - Validate image format (PNG, JPEG, WebP)
    - _Requirements: 5.3, 5.7_

  - [ ] 2.5 Write property test for dimension extraction

    - **Property 1: Image Download and Dimension Extraction**
    - **Validates: Requirements 1.1, 5.2, 5.3**

  - [x] 2.6 Implement base64 conversion
    - Convert image bytes to base64 string
    - Ensure format compatibility with LLM APIs
    - _Requirements: 5.4_

  - [x] 2.7 Write property test for base64 conversion

    - **Property 15: Base64 Conversion**
    - **Validates: Requirements 5.4**

  - [ ]* 2.8 Write unit tests for error scenarios
    - Test invalid URL format (error code 1001)
    - Test download failure (error code 1001)
    - Test invalid image format (error code 1001)
    - _Requirements: 5.5, 5.6, 1.5_

- [x] 3. Implement Prompt Builder component
  - [x] 3.1 Create PromptBuilder class with template loading
    - Load system prompt from prompts/active/screenshot_parse_system.txt
    - Create user prompt template with JSON schema
    - _Requirements: 3.1, 3.2_

  - [x] 3.2 Write property test for prompt construction

    - **Property 8: Prompt Construction Completeness**
    - **Validates: Requirements 3.1, 3.2**

  - [x] 3.3 Implement option-based prompt customization
    - Add two-column layout hints when force_two_columns=true
    - Add app-specific hints based on app_type
    - _Requirements: 6.6, 6.7_

  - [ ]* 3.4 Write property test for prompt customization
    - **Property 16: Prompt Customization Based on Options**
    - **Validates: Requirements 6.6, 6.7**

  - [ ]* 3.5 Write unit tests for prompt templates
    - Verify system prompt contains required elements
    - Verify user prompt includes JSON schema
    - Test different option combinations

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Multimodal LLM Client
  - [x] 5.1 Create MultimodalLLMClient base class and provider interface
    - Define VisionProvider protocol
    - Create provider registry
    - _Requirements: 3.3_

  - [x] 5.2 Implement OpenAI Vision provider
    - Use OpenAI SDK for GPT-4V/GPT-4o calls
    - Handle API errors and rate limits
    - Track tokens and costs
    - _Requirements: 3.4_

  - [x] 5.3 Implement Gemini Vision provider
    - Use Google Generative AI SDK
    - Handle API errors and rate limits
    - Track tokens and costs
    - _Requirements: 3.4_

  - [x] 5.4 Implement Claude Vision provider
    - Use Anthropic SDK for Claude 3 calls
    - Handle API errors and rate limits
    - Track tokens and costs
    - _Requirements: 3.4_

  - [x] 5.5 Implement JSON parsing with fallback
    - Parse LLM response as JSON
    - Extract JSON from markdown code blocks if needed
    - Handle malformed JSON responses
    - _Requirements: 3.5, 3.6_

  - [x] 5.6 Write property test for LLM invocation

    - **Property 2: LLM Invocation with Complete Parameters**
    - **Validates: Requirements 1.2, 3.4**

  - [ ]* 5.7 Write property test for JSON parsing
    - **Property 9: JSON Parsing with Fallback**
    - **Validates: Requirements 3.5, 3.6**

  - [ ]* 5.8 Write unit tests for provider failures
    - Test LLM call failure (error code 1002)
    - Test invalid JSON response (error code 1003)
    - Test provider fallback logic
    - _Requirements: 1.6, 1.7_

- [x] 6. Implement Result Normalizer component
  - [x] 6.1 Create ResultNormalizer class with field validation
    - Validate required fields presence
    - Validate sender and column values
    - Validate bounding box coordinates
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 6.2 Write property test for bubble completeness

    - **Property 5: Bubble Completeness and Validity**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 4.2, 4.3, 4.4, 9.8, 9.9**

  - [x] 6.3 Implement center point calculation
    - Calculate center_x and center_y from bounding box
    - Apply only when values are missing
    - _Requirements: 4.5_

  - [x] 6.4 Write property test for center calculation

    - **Property 10: Center Point Calculation**
    - **Validates: Requirements 4.5**

  - [x] 6.5 Implement bubble sorting
    - Sort bubbles by y1 coordinate (ascending)
    - Maintain stable sort for equal y1 values
    - _Requirements: 4.6_

  - [x] 6.6 Write property test for bubble sorting

    - **Property 11: Bubble Sorting by Vertical Position**
    - **Validates: Requirements 4.6**

  - [x] 6.7 Implement default value assignment
    - Assign confidence=0.5 when missing
    - Generate bubble_id when missing
    - _Requirements: 4.7_

  - [x] 6.8 Write property test for default confidence

    - **Property 12: Default Confidence Assignment**
    - **Validates: Requirements 4.7**

  - [x] 6.9 Implement fallback logic for invalid attribution
    - Infer sender from center_x position
    - Infer column from center_x position
    - Apply when values are missing or invalid
    - _Requirements: 4.8, 7.7, 7.8_

  - [x] 6.10 Write property test for fallback logic

    - **Property 13: Fallback Logic for Invalid Attribution**
    - **Validates: Requirements 4.8, 7.7, 7.8**

  - [x] 6.11 Implement bubble ID uniqueness enforcement
    - Check for duplicate bubble_ids
    - Generate unique IDs when duplicates found
    - _Requirements: 2.6, 4.9_

  - [x] 6.12 Write property test for bubble ID uniqueness

    - **Property 6: Bubble ID Uniqueness**
    - **Validates: Requirements 2.6, 4.9**

  - [x] 6.13 Write unit tests for missing field handling

    - Test missing required fields (error code 1004)
    - Test normalization with partial data
    - _Requirements: 1.8, 4.1_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Screenshot Parser Service
  - [x] 8.1 Create ScreenshotParserService class
    - Initialize with all component dependencies
    - Implement main parse_screenshot method
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 8.2 Implement workflow orchestration
    - Call ImageFetcher to download and process image
    - Call PromptBuilder to construct prompts
    - Call MultimodalLLMClient to get LLM response
    - Call ResultNormalizer to validate and normalize output
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 8.3 Write property test for output normalization

    - **Property 3: Output Structure Normalization**
    - **Validates: Requirements 1.3, 4.1**

  - [x] 8.4 Implement error handling and mapping
    - Map component errors to error codes (1001-1004)
    - Create error responses with descriptive messages
    - Log errors with context
    - _Requirements: 1.5, 1.6, 1.7, 1.8, 7.1, 7.2, 7.3, 7.4_

  - [x] 8.5 Implement low confidence marking
    - Mark bubbles with confidence < 0.3 for review
    - Add metadata for fallback processing
    - _Requirements: 7.5_

  - [x] 8.6 Write property test for low confidence marking

    - **Property 17: Low Confidence Marking**
    - **Validates: Requirements 7.5**

  - [x] 8.7 Implement cost and session tracking
    - Track LLM provider, model, tokens, and cost
    - Preserve session_id through pipeline
    - Add metadata to response
    - _Requirements: 8.6, 8.7_

  - [x] 8.8 Write property test for metadata tracking

    - **Property 18: Cost and Session Tracking Metadata**
    - **Validates: Requirements 8.6, 8.7**

  - [x] 8.9 Write unit tests for error code mapping

    - Test each error scenario returns correct code
    - Verify error messages are descriptive

- [x] 9. Implement API endpoint
  - [x] 9.1 Create FastAPI router in app/api/screenshot.py
    - Define POST /api/v1/chat_screenshot/parse endpoint
    - Add request/response models
    - Add OpenAPI documentation
    - _Requirements: 1.1_

  - [x] 9.2 Implement request validation
    - Validate image_url format
    - Validate optional parameters
    - Handle validation errors
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 9.3 Wire endpoint to ScreenshotParserService
    - Inject service via dependency injection
    - Call service.parse_screenshot
    - Return response
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 9.4 Write property test for response structure

    - **Property 19: Response Structure Completeness**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.10**

  - [x] 9.5 Write unit tests for API endpoint

    - Test successful parse request
    - Test validation errors
    - Test error responses with correct status codes

- [x] 10. Implement pipeline integration utilities
  - [x] 10.1 Create conversion function bubbles_to_dialogs
    - Convert ChatBubble list to dialogs format
    - Map sender to speaker field
    - Preserve text content
    - _Requirements: 8.2_

  - [x] 10.2 Write property test for pipeline compatibility

    - **Property 4: Pipeline Format Compatibility**
    - **Validates: Requirements 1.4, 8.1, 8.2**

  - [x] 10.3 Create layout validation function
    - Validate layout type and role mappings
    - Ensure consistency with bubble sender attribution
    - _Requirements: 2.9, 2.10_

  - [x] 10.4 Write property test for layout validity

    - **Property 7: Layout Structure Validity**
    - **Validates: Requirements 2.9, 2.10**

  - [x] 10.5 Write integration tests

    - Test end-to-end flow from screenshot URL to GenerateReplyRequest
    - Test with various chat app screenshots
    - Verify integration with existing orchestrator

- [x] 11. Add configuration and dependency injection
  - [x] 11.1 Add MultimodalLLMConfig to app/core/config.py
    - Add provider selection settings
    - Add API key configuration
    - Add timeout and retry settings
    - _Requirements: 3.3_

  - [x] 11.2 Update dependency injection in app/core/dependencies.py
    - Create factory for ScreenshotParserService
    - Wire all component dependencies
    - Add to FastAPI app

  - [x] 11.3 Update main.py to include screenshot router
    - Import and include screenshot router
    - Add to API prefix

- [x] 12. Create prompt templates
  - [x] 12.1 Create prompts/active/screenshot_parse_system.txt
    - Write system prompt defining parsing task
    - Include output format requirements
    - _Requirements: 3.1_

  - [x] 12.2 Add prompt to registry
    - Update prompts/registry.json
    - Add version metadata

- [x] 13. Final checkpoint - Integration testing
  - [x] 13.1 Test with real chat screenshots
    - Test WeChat screenshots
    - Test WhatsApp screenshots
    - Test LINE screenshots
    - Verify accuracy and completeness

  - [x] 13.2 Test error scenarios
    - Test with invalid URLs
    - Test with non-image URLs
    - Test with corrupted images
    - Verify error codes and messages

  - [x] 13.3 Test integration with generation pipeline
    - Parse screenshot → convert to dialogs → generate reply
    - Verify end-to-end flow works correctly

  - [x] 13.4 Performance and cost testing
    - Measure latency for different image sizes
    - Track LLM costs per parse
    - Verify cost tracking accuracy

  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation follows a bottom-up approach: components first, then integration, then API
- All code should follow existing patterns from app/services/orchestrator.py and app/services/llm_adapter.py
