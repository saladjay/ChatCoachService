# Requirements Document

## Introduction

This feature adds a multimodal AI-powered chat screenshot parsing service that extracts structured conversation data from chat application screenshots. The service uses vision-capable large language models to identify chat bubbles, extract text content, determine sender attribution, and recognize participant nicknames. This structured output integrates seamlessly with the existing conversation generation pipeline.

## Glossary

- **Chat_Screenshot_Parser**: The service that processes chat screenshots and extracts structured conversation data
- **Multimodal_LLM**: A large language model with vision capabilities (e.g., GPT-4V, Gemini Vision, Claude Vision)
- **Chat_Bubble**: A visual element in a chat interface containing a message
- **Sender_Attribution**: The identification of whether a message was sent by the user or the conversation partner
- **Bounding_Box**: Rectangular coordinates (x1, y1, x2, y2) defining a chat bubble's position
- **Confidence_Score**: A numerical value (0.0-1.0) indicating the model's certainty in its extraction
- **Layout_Type**: The visual arrangement pattern of chat bubbles (e.g., two_columns)
- **Participant**: A person involved in the conversation (self or other)
- **Image_Fetcher**: Component responsible for downloading and validating images
- **Prompt_Builder**: Component that constructs prompts for the multimodal LLM
- **Result_Normalizer**: Component that validates and standardizes LLM output
- **Fallback_Strategy**: Rule-based processing when LLM extraction fails or has low confidence

## Requirements

### Requirement 1: Chat Screenshot Parsing API

**User Story:** As a developer, I want to submit a chat screenshot URL and receive structured conversation data, so that I can integrate it with the existing conversation generation pipeline.

#### Acceptance Criteria

1. WHEN a valid image URL is provided, THE Chat_Screenshot_Parser SHALL download the image and extract its dimensions
2. WHEN the image is processed, THE Chat_Screenshot_Parser SHALL invoke the Multimodal_LLM with appropriate prompts
3. WHEN the LLM returns results, THE Chat_Screenshot_Parser SHALL validate and normalize the output structure
4. THE Chat_Screenshot_Parser SHALL return a response matching the format expected by the conversation generation pipeline
5. WHEN an invalid image URL is provided, THE Chat_Screenshot_Parser SHALL return an error with code 1001
6. WHEN the LLM call fails, THE Chat_Screenshot_Parser SHALL return an error with code 1002
7. WHEN the LLM returns invalid JSON, THE Chat_Screenshot_Parser SHALL return an error with code 1003
8. WHEN required fields are missing from LLM output, THE Chat_Screenshot_Parser SHALL return an error with code 1004

### Requirement 2: Structured Data Extraction

**User Story:** As a system, I want to extract detailed information from chat screenshots, so that I can understand conversation context and participant roles.

#### Acceptance Criteria

1. FOR EACH chat bubble in the screenshot, THE Chat_Screenshot_Parser SHALL extract the bounding box coordinates (x1, y1, x2, y2)
2. FOR EACH chat bubble, THE Chat_Screenshot_Parser SHALL extract the text content
3. FOR EACH chat bubble, THE Chat_Screenshot_Parser SHALL determine the sender attribution (user or talker)
4. FOR EACH chat bubble, THE Chat_Screenshot_Parser SHALL calculate the center point (center_x, center_y)
5. FOR EACH chat bubble, THE Chat_Screenshot_Parser SHALL determine the column position (left or right)
6. FOR EACH chat bubble, THE Chat_Screenshot_Parser SHALL assign a unique bubble_id within the screenshot
7. FOR EACH chat bubble, THE Chat_Screenshot_Parser SHALL include a confidence score
8. THE Chat_Screenshot_Parser SHALL identify participant nicknames when present in the screenshot
9. THE Chat_Screenshot_Parser SHALL determine the overall layout type (e.g., two_columns)
10. THE Chat_Screenshot_Parser SHALL map layout columns to participant roles (left_role, right_role)

### Requirement 3: Multimodal LLM Integration

**User Story:** As a system, I want to use vision-capable LLMs to parse chat screenshots, so that I can handle diverse chat applications and UI variations.

#### Acceptance Criteria

1. THE Prompt_Builder SHALL construct a system prompt that defines the parsing task and output format
2. THE Prompt_Builder SHALL construct a user prompt that includes parsing rules and JSON schema
3. THE Chat_Screenshot_Parser SHALL support multiple Multimodal_LLM providers (OpenAI, Gemini, Claude)
4. WHEN calling the Multimodal_LLM, THE Chat_Screenshot_Parser SHALL include the image and constructed prompts
5. THE Chat_Screenshot_Parser SHALL parse the LLM response as JSON
6. WHEN the LLM response is not valid JSON, THE Chat_Screenshot_Parser SHALL attempt to extract JSON from the response text
7. THE Chat_Screenshot_Parser SHALL log all LLM interactions for debugging and monitoring

### Requirement 4: Result Validation and Normalization

**User Story:** As a system, I want to validate and normalize LLM output, so that downstream services receive consistent, reliable data.

#### Acceptance Criteria

1. THE Result_Normalizer SHALL validate that all required fields are present in the LLM output
2. THE Result_Normalizer SHALL verify that sender values are either "user" or "talker"
3. THE Result_Normalizer SHALL verify that column values are either "left" or "right"
4. THE Result_Normalizer SHALL verify that bounding box coordinates are valid numbers
5. THE Result_Normalizer SHALL calculate center_x and center_y if not provided by the LLM
6. THE Result_Normalizer SHALL sort bubbles by vertical position (y1 ascending)
7. WHEN confidence scores are missing, THE Result_Normalizer SHALL assign a default value of 0.5
8. WHEN sender or column values are invalid, THE Result_Normalizer SHALL apply fallback logic based on center_x position
9. THE Result_Normalizer SHALL ensure bubble_id values are unique within a screenshot

### Requirement 5: Image Processing

**User Story:** As a system, I want to download and validate images from URLs, so that I can process them with the multimodal LLM.

#### Acceptance Criteria

1. WHEN an image URL is provided, THE Image_Fetcher SHALL validate the URL format
2. THE Image_Fetcher SHALL download the image from the provided URL
3. THE Image_Fetcher SHALL extract image dimensions (width, height)
4. THE Image_Fetcher SHALL convert the image to a format compatible with the Multimodal_LLM
5. WHEN the image download fails, THE Image_Fetcher SHALL raise an error
6. WHEN the image is not a valid image format, THE Image_Fetcher SHALL raise an error
7. THE Image_Fetcher SHALL support common image formats (PNG, JPEG, WebP)

### Requirement 6: Optional Parameters and Customization

**User Story:** As a developer, I want to provide optional parameters to customize parsing behavior, so that I can optimize results for specific scenarios.

#### Acceptance Criteria

1. THE Chat_Screenshot_Parser SHALL accept an optional session_id for request tracking
2. THE Chat_Screenshot_Parser SHALL accept an optional need_nickname flag
3. THE Chat_Screenshot_Parser SHALL accept an optional need_sender flag
4. THE Chat_Screenshot_Parser SHALL accept an optional force_two_columns flag
5. THE Chat_Screenshot_Parser SHALL accept an optional app_type parameter (wechat, line, whatsapp, unknown)
6. WHEN force_two_columns is true, THE Prompt_Builder SHALL include two-column layout assumptions in the prompt
7. WHEN app_type is specified, THE Prompt_Builder SHALL include app-specific parsing hints in the prompt
8. WHEN need_nickname is false, THE Chat_Screenshot_Parser MAY omit nickname extraction

### Requirement 7: Error Handling and Fallback

**User Story:** As a system, I want robust error handling and fallback strategies, so that the service remains reliable even when LLM extraction fails.

#### Acceptance Criteria

1. WHEN the image download fails, THE Chat_Screenshot_Parser SHALL return error code 1001 with a descriptive message
2. WHEN the Multimodal_LLM call fails, THE Chat_Screenshot_Parser SHALL return error code 1002 with a descriptive message
3. WHEN the LLM returns invalid JSON, THE Chat_Screenshot_Parser SHALL return error code 1003 with a descriptive message
4. WHEN required fields are missing, THE Chat_Screenshot_Parser SHALL return error code 1004 with a descriptive message
5. WHEN confidence scores are below a threshold, THE Chat_Screenshot_Parser SHALL mark bubbles for potential fallback processing
6. THE Chat_Screenshot_Parser SHALL log all errors with sufficient context for debugging
7. WHEN sender attribution is missing or invalid, THE Fallback_Strategy SHALL infer sender based on center_x position
8. WHEN column attribution is missing, THE Fallback_Strategy SHALL infer column based on center_x position

### Requirement 8: Integration with Existing Pipeline

**User Story:** As a system architect, I want the screenshot parser output to integrate seamlessly with existing services, so that parsed data can flow through the conversation generation pipeline.

#### Acceptance Criteria

1. THE Chat_Screenshot_Parser SHALL output a structure compatible with the conversation generation pipeline
2. THE bubbles array SHALL be convertible to the dialogs format expected by GenerateReplyRequest
3. THE participants data SHALL be usable for user profile and intimacy analysis
4. THE layout information SHALL be usable for conversation context building
5. THE Chat_Screenshot_Parser SHALL support the same language codes as the generation pipeline (en, ar, pt, es, zh-CN)
6. THE Chat_Screenshot_Parser SHALL include metadata that can be used for cost tracking and monitoring
7. THE Chat_Screenshot_Parser SHALL support session tracking for end-to-end observability

### Requirement 9: Response Format Standardization

**User Story:** As a developer, I want a standardized response format, so that I can reliably parse and use the API output.

#### Acceptance Criteria

1. THE Chat_Screenshot_Parser SHALL return responses with a code field (0 for success, non-zero for errors)
2. THE Chat_Screenshot_Parser SHALL return responses with a msg field describing the result
3. THE Chat_Screenshot_Parser SHALL return responses with a data field containing the parsed structure
4. THE data field SHALL include an image_meta object with width and height
5. THE data field SHALL include a participants object with self and other participant information
6. THE data field SHALL include a bubbles array with all extracted chat bubbles
7. THE data field SHALL include a layout object describing the visual arrangement
8. EACH bubble object SHALL include bubble_id, bbox, center_x, center_y, text, sender, column, and confidence
9. THE bbox object SHALL include x1, y1, x2, and y2 coordinates
10. THE participants object SHALL include id and nickname for each participant
