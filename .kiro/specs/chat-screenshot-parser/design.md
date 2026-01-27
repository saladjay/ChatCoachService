# Design Document

## Overview

The Chat Screenshot Parser is a new API service that leverages multimodal large language models (LLMs) to extract structured conversation data from chat application screenshots. This service addresses the limitations of rule-based visual detection systems by using AI vision capabilities to handle diverse chat UIs, complex layouts, and varied message formats.

The service integrates seamlessly with the existing conversation generation pipeline by outputting data in a format compatible with the `GenerateReplyRequest` model, enabling downstream services to process screenshot-derived conversations identically to manually-entered conversations.

## Architecture

### High-Level Flow

```
Client Request (image_url + options)
        ↓
API Endpoint (/api/chat_screenshot/parse)
        ↓
Image Fetcher (download & validate)
        ↓
Prompt Builder (construct multimodal prompts)
        ↓
Multimodal LLM Client (GPT-4V/Gemini/Claude)
        ↓
Result Normalizer (validate & standardize)
        ↓
Response (structured JSON)
```

### Component Architecture

The system follows a layered architecture similar to the existing conversation generation service:

1. **API Layer** (`app/api/screenshot.py`): FastAPI router handling HTTP requests
2. **Service Layer** (`app/services/screenshot_parser.py`): Core business logic
3. **Adapter Layer** (`app/services/multimodal_llm_adapter.py`): LLM provider abstraction
4. **Model Layer** (`app/models/screenshot.py`): Pydantic models for request/response

This architecture mirrors the existing pattern used in `app/api/generate.py` and `app/services/orchestrator.py`.

## Components and Interfaces

### 1. API Endpoint

**Module**: `app/api/screenshot.py`

**Endpoint**: `POST /api/v1/chat_screenshot/parse`

**Request Model**:
```python
class ParseScreenshotRequest(BaseModel):
    image_url: str = Field(..., description="Public URL of chat screenshot")
    session_id: str | None = Field(None, description="Optional session ID for tracking")
    options: ParseOptions | None = Field(None, description="Optional parsing parameters")

class ParseOptions(BaseModel):
    need_nickname: bool = Field(True, description="Extract participant nicknames")
    need_sender: bool = Field(True, description="Determine sender attribution")
    force_two_columns: bool = Field(True, description="Assume two-column layout")
    app_type: Literal["wechat", "line", "whatsapp", "unknown"] = Field("unknown")
```

**Response Model**:
```python
class ParseScreenshotResponse(BaseModel):
    code: int = Field(..., description="Status code (0=success)")
    msg: str = Field(..., description="Status message")
    data: ParsedScreenshotData | None = Field(None, description="Parsed data")

class ParsedScreenshotData(BaseModel):
    image_meta: ImageMeta
    participants: Participants
    bubbles: list[ChatBubble]
    layout: LayoutInfo

class ImageMeta(BaseModel):
    width: int
    height: int

class Participants(BaseModel):
    self: Participant
    other: Participant

class Participant(BaseModel):
    id: str
    nickname: str

class ChatBubble(BaseModel):
    bubble_id: str
    bbox: BoundingBox
    center_x: int
    center_y: int
    text: str
    sender: Literal["user", "talker"]
    column: Literal["left", "right"]
    confidence: float = Field(ge=0.0, le=1.0)

class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int

class LayoutInfo(BaseModel):
    type: str = Field(default="two_columns")
    left_role: Literal["user", "talker"]
    right_role: Literal["user", "talker"]
```

### 2. Screenshot Parser Service

**Module**: `app/services/screenshot_parser.py`

**Class**: `ScreenshotParserService`

**Key Methods**:
```python
class ScreenshotParserService:
    def __init__(
        self,
        image_fetcher: ImageFetcher,
        prompt_builder: PromptBuilder,
        llm_client: MultimodalLLMClient,
        result_normalizer: ResultNormalizer,
    ):
        ...
    
    async def parse_screenshot(
        self,
        request: ParseScreenshotRequest,
    ) -> ParseScreenshotResponse:
        """Main entry point for screenshot parsing."""
        ...
```

**Responsibilities**:
- Coordinate the parsing workflow
- Handle errors and map to appropriate error codes
- Log execution for observability
- Return standardized responses

### 3. Image Fetcher

**Module**: `app/services/image_fetcher.py`

**Class**: `ImageFetcher`

**Key Methods**:
```python
class ImageFetcher:
    async def fetch_image(self, url: str) -> FetchedImage:
        """Download and validate image from URL."""
        ...
    
    def _validate_url(self, url: str) -> None:
        """Validate URL format and accessibility."""
        ...
    
    def _extract_dimensions(self, image_bytes: bytes) -> tuple[int, int]:
        """Extract image width and height."""
        ...
    
    def _convert_to_base64(self, image_bytes: bytes) -> str:
        """Convert image to base64 for LLM API."""
        ...

class FetchedImage:
    url: str
    width: int
    height: int
    base64_data: str
    format: str  # png, jpeg, webp
```

**Dependencies**: `httpx` for async HTTP, `Pillow` for image processing

### 4. Prompt Builder

**Module**: `app/services/prompt_builder.py`

**Class**: `PromptBuilder`

**Key Methods**:
```python
class PromptBuilder:
    def build_prompts(
        self,
        options: ParseOptions,
    ) -> tuple[str, str]:
        """Build system and user prompts for multimodal LLM.
        
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        ...
    
    def _build_system_prompt(self) -> str:
        """Build fixed system prompt defining the task."""
        ...
    
    def _build_user_prompt(self, options: ParseOptions) -> str:
        """Build dynamic user prompt with options and schema."""
        ...
    
    def _get_json_schema(self) -> str:
        """Get JSON schema template for LLM output."""
        ...
```

**Prompt Templates**:

System Prompt (stored in `prompts/active/screenshot_parse_system.txt`):
```
You are a specialized chat screenshot structure parser.

Your task:
1. Identify each chat bubble's bounding box (x1, y1, x2, y2)
2. Extract text content from each bubble
3. Determine sender attribution (user or talker)
4. Identify participant nicknames if visible

Requirements:
- Return strict JSON format
- All coordinates in original image pixels
- sender must be "user" or "talker"
- column must be "left" or "right"
- No explanatory text outside JSON
```

User Prompt Template:
```
Parse this chat screenshot.

Rules:
- Left bubbles typically belong to talker
- Right bubbles typically belong to user
- Extract nicknames from header/contact name if present

Return this exact JSON structure:
{schema_template}
```

### 5. Multimodal LLM Client

**Module**: `app/services/multimodal_llm_adapter.py`

**Class**: `MultimodalLLMClient`

**Key Methods**:
```python
class MultimodalLLMClient:
    def __init__(self, config: MultimodalLLMConfig):
        self.config = config
        self.providers = {
            "openai": OpenAIVisionProvider(),
            "gemini": GeminiVisionProvider(),
            "claude": ClaudeVisionProvider(),
        }
    
    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
        provider: str | None = None,
    ) -> MultimodalLLMResponse:
        """Call multimodal LLM with image and prompts."""
        ...
    
    def _select_provider(self) -> str:
        """Select provider based on availability and config."""
        ...
    
    def _parse_json_response(self, raw_text: str) -> dict:
        """Extract and parse JSON from LLM response."""
        ...

class MultimodalLLMResponse:
    raw_text: str
    parsed_json: dict
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
```

**Provider Implementations**:

Each provider implements a common interface:
```python
class VisionProvider(Protocol):
    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
    ) -> ProviderResponse:
        ...
```

Supported providers:
- **OpenAI**: GPT-4V, GPT-4o
- **Gemini**: Gemini 1.5 Pro, Gemini 1.5 Flash
- **Claude**: Claude 3 Opus, Claude 3 Sonnet

### 6. Result Normalizer

**Module**: `app/services/result_normalizer.py`

**Class**: `ResultNormalizer`

**Key Methods**:
```python
class ResultNormalizer:
    def normalize(
        self,
        raw_json: dict,
        image_meta: ImageMeta,
        options: ParseOptions,
    ) -> ParsedScreenshotData:
        """Validate and normalize LLM output."""
        ...
    
    def _validate_required_fields(self, data: dict) -> None:
        """Check all required fields are present."""
        ...
    
    def _normalize_bubbles(self, bubbles: list[dict]) -> list[ChatBubble]:
        """Normalize bubble data with validation and defaults."""
        ...
    
    def _calculate_center(self, bbox: BoundingBox) -> tuple[int, int]:
        """Calculate center point from bounding box."""
        ...
    
    def _infer_sender_from_position(self, center_x: int, width: int) -> str:
        """Infer sender based on horizontal position."""
        ...
    
    def _sort_bubbles_by_position(self, bubbles: list[ChatBubble]) -> list[ChatBubble]:
        """Sort bubbles by vertical position (y1 ascending)."""
        ...
    
    def _ensure_unique_ids(self, bubbles: list[ChatBubble]) -> None:
        """Ensure all bubble_ids are unique."""
        ...
```

**Normalization Rules**:
1. Calculate `center_x` and `center_y` if missing: `center_x = (x1 + x2) / 2`
2. Infer `sender` if missing: `center_x < width/2 → "talker"`, else `"user"`
3. Infer `column` if missing: `center_x < width/2 → "left"`, else `"right"`
4. Set default `confidence = 0.5` if missing
5. Generate `bubble_id` if missing: `f"b{index}"`
6. Sort bubbles by `y1` (top to bottom)
7. Validate `sender` ∈ {"user", "talker"}
8. Validate `column` ∈ {"left", "right"}

## Data Models

### Request Flow Data Models

```python
# Input to service
ParseScreenshotRequest
  ├── image_url: str
  ├── session_id: str | None
  └── options: ParseOptions
        ├── need_nickname: bool
        ├── need_sender: bool
        ├── force_two_columns: bool
        └── app_type: str

# Internal processing
FetchedImage
  ├── url: str
  ├── width: int
  ├── height: int
  ├── base64_data: str
  └── format: str

MultimodalLLMResponse
  ├── raw_text: str
  ├── parsed_json: dict
  ├── provider: str
  ├── model: str
  ├── input_tokens: int
  ├── output_tokens: int
  └── cost_usd: float

# Output from service
ParseScreenshotResponse
  ├── code: int
  ├── msg: str
  └── data: ParsedScreenshotData
        ├── image_meta: ImageMeta
        ├── participants: Participants
        ├── bubbles: list[ChatBubble]
        └── layout: LayoutInfo
```

### Integration with Existing Pipeline

The `ParsedScreenshotData.bubbles` array can be converted to the `dialogs` format expected by `GenerateReplyRequest`:

```python
def bubbles_to_dialogs(bubbles: list[ChatBubble]) -> list[dict]:
    """Convert bubbles to dialogs format for generation pipeline."""
    return [
        {
            "speaker": bubble.sender,
            "text": bubble.text,
            "timestamp": None,  # Not available from screenshot
        }
        for bubble in bubbles
    ]
```

This enables seamless integration:
```python
# Parse screenshot
parse_response = await screenshot_parser.parse_screenshot(parse_request)

# Convert to generation request
dialogs = bubbles_to_dialogs(parse_response.data.bubbles)
gen_request = GenerateReplyRequest(
    user_id=user_id,
    target_id=parse_response.data.participants.other.id,
    conversation_id=conversation_id,
    dialogs=dialogs,
    intimacy_value=50,  # Default or from user profile
)

# Generate reply
reply = await orchestrator.generate_reply(gen_request)
```


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Image Download and Dimension Extraction

*For any* valid image URL, when the Image_Fetcher downloads the image, it should successfully extract positive integer values for width and height.

**Validates: Requirements 1.1, 5.2, 5.3**

### Property 2: LLM Invocation with Complete Parameters

*For any* parse request, when the Chat_Screenshot_Parser processes it, the Multimodal_LLM should be invoked with both system prompt, user prompt, and image data.

**Validates: Requirements 1.2, 3.4**

### Property 3: Output Structure Normalization

*For any* LLM response (valid or invalid), when the Result_Normalizer processes it, the output should either be a valid ParsedScreenshotData structure or raise a specific error.

**Validates: Requirements 1.3, 4.1**

### Property 4: Pipeline Format Compatibility

*For any* successful parse response, the bubbles array should be convertible to the dialogs format expected by GenerateReplyRequest without data loss.

**Validates: Requirements 1.4, 8.1, 8.2**

### Property 5: Bubble Completeness and Validity

*For any* bubble in the output bubbles array, it should contain all required fields (bubble_id, bbox with x1/y1/x2/y2, center_x, center_y, text, sender, column, confidence) with valid values (sender ∈ {"user", "talker"}, column ∈ {"left", "right"}, confidence ∈ [0.0, 1.0], bbox coordinates are numbers).

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 4.2, 4.3, 4.4, 9.8, 9.9**

### Property 6: Bubble ID Uniqueness

*For any* set of bubbles in a parse response, all bubble_id values should be unique within that response.

**Validates: Requirements 2.6, 4.9**

### Property 7: Layout Structure Validity

*For any* successful parse response, the layout object should have a valid type and both left_role and right_role should be either "user" or "talker".

**Validates: Requirements 2.9, 2.10**

### Property 8: Prompt Construction Completeness

*For any* ParseOptions configuration, the Prompt_Builder should generate both a system prompt containing task definition and a user prompt containing parsing rules and JSON schema.

**Validates: Requirements 3.1, 3.2**

### Property 9: JSON Parsing with Fallback

*For any* LLM response text, the parser should either successfully extract valid JSON or attempt to extract JSON from within the text before failing.

**Validates: Requirements 3.5, 3.6**

### Property 10: Center Point Calculation

*For any* bubble with a bounding box, if center_x or center_y are not provided by the LLM, the Result_Normalizer should calculate them as center_x = (x1 + x2) / 2 and center_y = (y1 + y2) / 2.

**Validates: Requirements 4.5**

### Property 11: Bubble Sorting by Vertical Position

*For any* set of bubbles, the output bubbles array should be sorted in ascending order by y1 coordinate (top to bottom).

**Validates: Requirements 4.6**

### Property 12: Default Confidence Assignment

*For any* bubble missing a confidence score, the Result_Normalizer should assign a default value of 0.5.

**Validates: Requirements 4.7**

### Property 13: Fallback Logic for Invalid Attribution

*For any* bubble with missing or invalid sender/column values, the Result_Normalizer should infer them based on center_x position: if center_x < image_width/2, then sender="talker" and column="left", otherwise sender="user" and column="right".

**Validates: Requirements 4.8, 7.7, 7.8**

### Property 14: URL Format Validation

*For any* image URL provided, the Image_Fetcher should validate that it is a properly formatted HTTP/HTTPS URL before attempting download.

**Validates: Requirements 5.1**

### Property 15: Base64 Conversion

*For any* successfully downloaded image, the Image_Fetcher should convert it to valid base64-encoded string format.

**Validates: Requirements 5.4**

### Property 16: Prompt Customization Based on Options

*For any* ParseOptions with force_two_columns=true or app_type specified, the generated user prompt should include corresponding layout assumptions or app-specific hints.

**Validates: Requirements 6.6, 6.7**

### Property 17: Low Confidence Marking

*For any* bubble with confidence score below a threshold (e.g., 0.3), the system should mark it for potential fallback processing or manual review.

**Validates: Requirements 7.5**

### Property 18: Cost and Session Tracking Metadata

*For any* successful parse response, the system should include metadata for cost tracking (provider, model, tokens) and session tracking (session_id if provided).

**Validates: Requirements 8.6, 8.7**

### Property 19: Response Structure Completeness

*For any* response from the Chat_Screenshot_Parser, it should include code (integer), msg (string), and for successful responses (code=0), a data object containing image_meta, participants, bubbles, and layout.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.10**

## Error Handling

### Error Codes and Scenarios

The system uses specific error codes to distinguish failure modes:

| Code | Scenario | Handling |
|------|----------|----------|
| 0 | Success | Return parsed data |
| 1001 | Image download failure | Log URL, return error response |
| 1002 | LLM call failure | Log provider/model, return error response |
| 1003 | Invalid JSON response | Log raw response, return error response |
| 1004 | Missing required fields | Log missing fields, return error response |

### Error Response Format

```python
{
    "code": 1001,
    "msg": "Failed to download image from URL",
    "data": null
}
```

### Fallback Strategies

1. **Invalid Sender/Column**: Infer from center_x position
2. **Missing Center Coordinates**: Calculate from bounding box
3. **Missing Confidence**: Default to 0.5
4. **Missing Bubble ID**: Generate sequential IDs
5. **LLM Provider Failure**: Retry with alternative provider (if configured)

### Logging Requirements

All errors should be logged with:
- Request ID / Session ID
- Error code and message
- Relevant context (URL, provider, model, etc.)
- Stack trace for unexpected errors

## Testing Strategy

### Dual Testing Approach

The testing strategy employs both unit tests and property-based tests to ensure comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs

Both approaches are complementary and necessary for comprehensive coverage.

### Property-Based Testing

Property-based tests will use the **Hypothesis** library for Python to generate random test inputs and verify that correctness properties hold across many iterations.

**Configuration**:
- Minimum 100 iterations per property test
- Each test tagged with: `# Feature: chat-screenshot-parser, Property {N}: {property_text}`

**Test Coverage**:

1. **Property 1-4**: Test with various valid/invalid image URLs and LLM responses
2. **Property 5-7**: Generate random bubble data with valid/invalid fields
3. **Property 8-9**: Test prompt generation with various options and JSON parsing
4. **Property 10-13**: Test normalization logic with missing/invalid data
5. **Property 14-15**: Test URL validation and image conversion
6. **Property 16-17**: Test option-based customization and confidence thresholds
7. **Property 18-19**: Test metadata and response structure completeness

**Generators**:
- `arbitrary_image_url()`: Generate valid/invalid URLs
- `arbitrary_bbox()`: Generate bounding boxes with valid/invalid coordinates
- `arbitrary_bubble()`: Generate chat bubbles with various field combinations
- `arbitrary_llm_response()`: Generate LLM responses with valid/invalid JSON
- `arbitrary_parse_options()`: Generate various option combinations

### Unit Testing

Unit tests focus on:

1. **Specific Error Codes**: Test that each error scenario returns the correct code
   - Invalid URL → 1001
   - LLM failure → 1002
   - Invalid JSON → 1003
   - Missing fields → 1004

2. **Edge Cases**:
   - Empty bubbles array
   - Single bubble
   - Overlapping bounding boxes
   - Extreme coordinate values
   - Very long text content

3. **Integration Points**:
   - Image fetcher with real HTTP requests (mocked)
   - LLM client with different providers
   - Conversion to GenerateReplyRequest format

4. **Prompt Templates**:
   - Verify system prompt contains required elements
   - Verify user prompt includes schema
   - Verify option-based customization

### Test Organization

```
tests/
├── unit/
│   ├── test_image_fetcher.py
│   ├── test_prompt_builder.py
│   ├── test_multimodal_llm_client.py
│   ├── test_result_normalizer.py
│   └── test_screenshot_parser_service.py
├── property/
│   ├── test_bubble_properties.py
│   ├── test_normalization_properties.py
│   ├── test_response_properties.py
│   └── test_integration_properties.py
└── integration/
    └── test_end_to_end.py
```

### Testing Guidelines

- **Avoid over-testing**: Focus on core functional logic and important edge cases
- **Limit verification attempts**: Maximum 2 tries for fixing failing tests
- **No mocks for property tests**: Tests must validate real functionality
- **Property test failures**: Analyze counterexamples to determine if test, code, or spec needs adjustment
