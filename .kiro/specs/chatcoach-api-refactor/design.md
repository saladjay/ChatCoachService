# Design Document

## Overview

This document describes the design for refactoring the ChatCoach API to align with the old-api service structure while maintaining compatibility with the existing Orchestrator and integrating the screenshotanalysis library from the core/ directory. The refactor will introduce a new `/api/v1/ChatCoach` endpoint structure that provides screenshot analysis and reply generation capabilities.

The design follows a layered architecture:
- **API Layer**: FastAPI routers handling HTTP requests/responses
- **Service Layer**: Business logic for screenshot processing and orchestration
- **Integration Layer**: Adapters for screenshotanalysis library and external services
- **Configuration Layer**: Centralized configuration management

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Health  │  │ Predict  │  │ Metrics  │  │  Router  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
┌───────┼─────────────┼─────────────┼─────────────┼──────────┐
│       │      Service Layer         │             │          │
│  ┌────▼──────┐  ┌──▼──────────────▼──┐  ┌───────▼──────┐  │
│  │  Status   │  │  Screenshot        │  │  Metrics     │  │
│  │  Checker  │  │  Processor         │  │  Collector   │  │
│  └───────────┘  └──┬──────────────┬──┘  └──────────────┘  │
└────────────────────┼──────────────┼──────────────────────
─┘
        │              │
┌───────┼──────────────┼──────────────────────────────────────┐
│       │   Integration Layer                                  │
│  ┌────▼──────────────▼──────┐  ┌──────────────────────┐    │
│  │  Screenshotanalysis      │  │  Orchestrator        │    │
│  │  (Text/Layout Detection) │  │  (Reply Generation)  │    │
│  └──────────────────────────┘  └──────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### Request Flow

1. **Health Check Flow**:
   ```
   Client → /health → StatusChecker → Model Status → Response
   ```

2. **Screenshot Analysis Flow**:
   ```
   Client → /predict → ScreenshotProcessor → screenshotanalysis
                                           → Format Results
                                           → [Optional] Orchestrator
                                           → Response
   ```

3. **Metrics Flow**:
   ```
   Client → /metrics → MetricsCollector → Prometheus Format → Response
   ```

## Components and Interfaces

### 1. API Router (`app/api/v1/router.py`)

**Purpose**: Central router that aggregates all v1 endpoints under `/api/v1/ChatCoach` prefix.

**Interface**:
```python
from fastapi import APIRouter
from app.api.v1 import health, predict, chat_analysis

api_router = APIRouter(prefix="/api/v1/ChatCoach")
api_router.include_router(health.router)
api_router.include_router(predict.router)
api_router.include_router(chat_analysis.router)
```

**Responsibilities**:
- Aggregate sub-routers
- Apply common prefix
- Enable versioning through URL structure

### 2. Health Endpoint (`app/api/v1/health.py`)

**Purpose**: Provide service health status and model availability checks.

**Request Model**:
```python
# No request body - GET endpoint
```

**Response Models**:
```python
class HealthResponse(BaseModel):
    status: str  # "healthy" or "unhealthy"
    timestamp: datetime
    version: str
    models: dict[str, bool]  # Model availability status

class ErrorResponse(BaseModel):
    detail: str
```

**Interface**:
```python
@router.get(
    "",
    response_model=HealthResponse,
    responses={401: {"model": ErrorResponse}}
)
async def health_check(
    status_checker: StatusCheckerDep
) -> HealthResponse:
    """Check service and model health"""
```

**Responsibilities**:
- Check screenshotanalysis model availability
- Return service version and timestamp
- Return HTTP 401 if models unavailable

### 3. Predict Endpoint (`app/api/v1/predict.py`)

**Purpose**: Analyze chat screenshots and optionally generate reply suggestions.

**Request Model**:
```python
class PredictRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1)
    app_name: str  # Validated against config
    language: str  # Validated against config
    user_id: str = Field(..., min_length=1)
    request_id: Optional[str] = None
    conf_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    reply: bool = False
```

**Response Models**:
```python
class DialogItem(BaseModel):
    position: list[float]  # [min_x, min_y, max_x, max_y] (0.0-1.0)
    text: str
    speaker: str  # "self" or speaker name
    from_user: bool

class ImageResult(BaseModel):
    url: str
    dialogs: list[DialogItem]

class PredictResponse(BaseModel):
    success: bool
    message: str
    user_id: str
    request_id: Optional[str]
    results: list[ImageResult]
    suggested_replies: Optional[list[str]] = None
```

**Interface**:
```python
@router.post("", response_model=PredictResponse)
async def predict(
    request: PredictRequest,
    processor: ScreenshotProcessorDep,
    orchestrator: OrchestratorDep
) -> PredictResponse:
    """Analyze screenshots and optionally generate replies"""
```

**Responsibilities**:
- Validate request parameters
- Process each screenshot URL
- Extract structured dialog data
- Optionally call Orchestrator for reply generation
- Return unified response

### 4. Metrics Endpoint (`app/api/v1/chat_analysis.py`)

**Purpose**: Expose Prometheus-compatible performance metrics.

**Interface**:
```python
@router.get("/metrics", response_class=PlainTextResponse)
async def get_metrics(
    metrics_collector: MetricsCollectorDep
) -> str:
    """Return Prometheus format metrics"""
```

**Responsibilities**:
- Collect request counts, latencies, error rates
- Format as Prometheus text format
- Track per-endpoint metrics

### 5. Screenshot Processor Service (`app/services/screenshot_processor.py`)

**Purpose**: Core service for processing chat screenshots using screenshotanalysis library.

**Interface**:
```python
class ScreenshotProcessor:
    def __init__(
        self,
        text_det_analyzer: TextDetAnalyzer,
        layout_det_analyzer: LayoutDetAnalyzer,
        text_rec_model: TextRecModel,
        config: ScreenshotConfig
    ):
        """Initialize with screenshotanalysis models"""
    
    async def process_screenshot(
        self,
        image_url: str,
        app_type: str,
        conf_threshold: Optional[float] = None
    ) -> ImageResult:
        """Process single screenshot and return structured dialogs"""
    
    def _load_models(self) -> None:
        """Lazy load screenshotanalysis models"""
    
    def _extract_text(
        self,
        text_box: TextBox,
        image: np.ndarray
    ) -> str:
        """Extract text from detected box using OCR"""
    
    def _identify_speaker(
        self,
        box: TextBox,
        nickname: Optional[str]
    ) -> tuple[str, bool]:
        """Identify speaker and whether message is from user"""
    
    def _normalize_coordinates(
        self,
        box: TextBox,
        padding: tuple,
        image_size: tuple
    ) -> list[float]:
        """Convert pixel coordinates to percentage (0.0-1.0)"""
```

**Responsibilities**:
- Load and manage screenshotanalysis models
- Perform text detection, layout detection, OCR
- Extract nickname and speaker information
- Group messages by speaker
- Normalize coordinates to percentages
- Handle model loading errors

### 6. Status Checker Service (`app/services/status_checker.py`)

**Purpose**: Check availability of screenshotanalysis models and service health.

**Interface**:
```python
class StatusChecker:
    def __init__(self):
        """Initialize status checker"""
    
    def check_models(self) -> dict[str, bool]:
        """Check if screenshotanalysis models are loaded"""
    
    def is_healthy(self) -> bool:
        """Check overall service health"""
```

**Responsibilities**:
- Verify text detection model availability
- Verify layout detection model availability
- Verify text recognition model availability
- Return aggregated health status

### 7. Metrics Collector Service (`app/services/metrics_collector.py`)

**Purpose**: Collect and format performance metrics for monitoring.

**Interface**:
```python
class MetricsCollector:
    def __init__(self):
        """Initialize metrics storage"""
    
    def record_request(
        self,
        endpoint: str,
        status_code: int,
        duration_ms: float
    ) -> None:
        """Record request metrics"""
    
    def get_prometheus_metrics(self) -> str:
        """Format metrics as Prometheus text"""
```

**Responsibilities**:
- Track request counts by endpoint
- Track response times
- Track error rates
- Format as Prometheus exposition format

## Data Models

### Configuration Models

```python
class ScreenshotConfig(BaseModel):
    """Configuration for screenshot processing"""
    supported_apps: list[str]  # ["whatsapp", "telegram", "discord", ...]
    supported_languages: list[str]  # ["en", "zh", "es", ...]
    default_conf_threshold: float = 0.5
    model_load_timeout: float = 30.0
    history_update_interval: int = 10  # Update every N calls

class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    submodule_level: str = "WARNING"  # For screenshotanalysis
```

### Internal Data Models

```python
class TextBox(BaseModel):
    """Detected text box from screenshotanalysis"""
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    confidence: float
    layout_det: str  # "text", "avatar", "nickname"

class ProcessedDialog(BaseModel):
    """Intermediate dialog representation"""
    speaker: str
    texts: list[str]
    positions: list[list[float]]
    from_user: bool
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Acceptance Criteria Testing Prework

**1.1 THE API_Router SHALL use the prefix "/api/v1/ChatCoach" for all endpoints**
Thoughts: This is a configuration property that applies to all endpoints. We can test this by making requests to various endpoints and verifying the URL structure.
Testable: yes - property

**1.2 THE API_Router SHALL organize endpoints into logical groups (health, predict, chat_analysis)**
Thoughts: This is about code organization and API structure. We can verify that the router includes the correct sub-routers.
Testable: yes - example

**2.1 WHEN a health check request is received, THE Health_Endpoint SHALL return service status, timestamp, and version**
Thoughts: This is a property about the response structure. For any health check request, the response should contain these fields.
Testable: yes - property

**2.2 IF the screenshotanalysis models are unavailable, THEN THE Health_Endpoint SHALL return HTTP 401**
Thoughts: This is testing error handling for a specific condition. We can simulate model unavailability and verify the response.
Testable: yes - example

**3.1 WHEN a predict request is received with image URLs, THE Predict_Endpoint SHALL analyze each screenshot and return structured dialog data**
Thoughts: This is a core functional property. For any valid request with image URLs, we should get structured dialog data back.
Testable: yes - property

**3.8 WHEN reply parameter is true, THEN THE Predict_Endpoint SHALL accept optional reply parameter (boolean) to request suggested replies**
Thoughts: This is testing conditional behavior. When reply=true, the endpoint should call the orchestrator.
Testable: yes - property

**4.6 THE Screenshot_Parser SHALL identify chat message speakers (self vs other)**
Thoughts: This is a property about speaker identification. For any screenshot with messages, speakers should be correctly identified.
Testable: yes - property

**4.8 THE Screenshot_Parser SHALL return normalized position coordinates as percentages (0.0-1.0)**
Thoughts: This is an invariant property. All position coordinates in the output should be within the 0.0-1.0 range.
Testable: yes - property

**4.9 THE Screenshot_Parser SHALL group consecutive messages by the same speaker**
Thoughts: This is a property about message grouping logic. Consecutive messages from the same speaker should be grouped together.
Testable: yes - property

**6.1 WHEN app_name is provided, THE API SHALL validate it against a list of supported chat applications**
Thoughts: This is input validation. Any app_name not in the supported list should be rejected.
Testable: yes - property

**6.2 WHEN language is provided, THE API SHALL validate it against a list of supported languages**
Thoughts: This is input validation. Any language not in the supported list should be rejected.
Testable: yes - property

**6.3 WHEN conf_threshold is provided, THE API SHALL validate it is between 0.0 and 1.0**
Thoughts: This is a boundary validation property. Any conf_threshold outside [0.0, 1.0] should be rejected.
Testable: yes - property

**8.2 THE Dialog_Item SHALL include position as [min_x, min_y, max_x, max_y] in percentage coordinates**
Thoughts: This is a structural property about the response format. All dialog items should have positions in this format.
Testable: yes - property

**8.5 THE Dialog_Item SHALL include from_user boolean field indicating if the message is from the user**
Thoughts: This is a required field property. All dialog items must have this field.
Testable: yes - property

### Property Reflection

After reviewing all testable properties, I identify the following consolidations:

1. **Properties 6.1, 6.2, 6.3** (validation properties) can be combined into a single comprehensive input validation property
2. **Properties 8.2, 8.5** (response structure properties) can be combined into a single response format property
3. **Property 4.8** (coordinate normalization) is already covered by **Property 8.2** (position format)

Consolidated properties:
- Combine 6.1, 6.2, 6.3 → Property 1: Input validation
- Combine 8.2, 8.5, 4.8 → Property 2: Response format
- Keep 1.1, 2.1, 3.1, 3.8, 4.6, 4.9 as separate properties

### Correctness Properties

**Property 1: API Endpoint Structure**
*For any* endpoint in the ChatCoach API, the URL path should start with "/api/v1/ChatCoach"
**Validates: Requirements 1.1**

**Property 2: Health Check Response Completeness**
*For any* successful health check request, the response should contain status, timestamp, version, and models fields
**Validates: Requirements 2.1**

**Property 3: Screenshot Analysis Completeness**
*For any* valid predict request with image URLs, each URL should produce an ImageResult with a dialogs array
**Validates: Requirements 3.1**

**Property 4: Reply Generation Integration**
*For any* predict request where reply=true and dialogs are extracted, the response should include suggested_replies field
**Validates: Requirements 3.8, 9.4**

**Property 5: Speaker Identification Consistency**
*For any* extracted dialog, the speaker field should be either "self" or a non-empty speaker name, and from_user should match (true for "self", false otherwise)
**Validates: Requirements 4.6**

**Property 6: Message Grouping Invariant**
*For any* sequence of consecutive messages from the same speaker, they should be grouped into a single dialog entry with combined text
**Validates: Requirements 4.9**

**Property 7: Input Validation**
*For any* predict request, if app_name is not in supported_apps OR language is not in supported_languages OR conf_threshold is outside [0.0, 1.0], the request should be rejected with a validation error
**Validates: Requirements 6.1, 6.2, 6.3**

**Property 8: Response Format Consistency**
*For any* dialog item in the response, it should have position as [min_x, min_y, max_x, max_y] where all values are in [0.0, 1.0], text as a non-empty string, speaker as a string, and from_user as a boolean
**Validates: Requirements 8.2, 8.5, 4.8**

**Property 9: Coordinate Normalization Bounds**
*For any* position coordinate in a dialog item, all four values (min_x, min_y, max_x, max_y) should satisfy: 0.0 ≤ value ≤ 1.0 AND min_x ≤ max_x AND min_y ≤ max_y
**Validates: Requirements 4.8**

## Error Handling

### Error Categories

1. **Model Unavailable (HTTP 401)**
   - Trigger: screenshotanalysis models not loaded
   - Response: `{"detail": "Model Unavailable"}`
   - Handling: Return immediately, log error

2. **Validation Error (HTTP 400)**
   - Trigger: Invalid request parameters
   - Response: `{"detail": "Validation error: <details>"}`
   - Handling: Pydantic validation, return descriptive message

3. **Image Load Error (HTTP 400)**
   - Trigger: Failed to download or process image
   - Response: `{"success": false, "message": "Load image failed: <details>"}`
   - Handling: Catch ImageLoader exceptions, return error response

4. **Inference Error (HTTP 500)**
   - Trigger: screenshotanalysis inference failure
   - Response: `{"success": false, "message": "Inference error: <details>"}`
   - Handling: Catch analysis exceptions, log and return error

5. **Orchestrator Error (HTTP 500)**
   - Trigger: Reply generation failure
   - Response: Return results without suggested_replies
   - Handling: Log error, continue with screenshot results

### Error Handling Strategy

```python
# Model availability check
if not models_loaded:
    raise HTTPException(status_code=401, detail="Model Unavailable")

# Image loading
try:
    image = ImageLoader.load_image(url)
except Exception as e:
    return PredictResponse(
        success=False,
        message=f"Load image failed: {str(e)}",
        ...
    )

# Screenshot analysis
try:
    results = processor.process_screenshot(...)
except AnalysisException as e:
    return PredictResponse(
        success=False,
        message=f"Inference error: {str(e)}",
        ...
    )

# Reply generation (non-blocking)
suggested_replies = None
if request.reply:
    try:
        suggested_replies = await orchestrator.generate_reply(...)
    except Exception as e:
        logger.error(f"Reply generation failed: {e}")
        # Continue without replies
```

## Testing Strategy

### Dual Testing Approach

We will implement both unit tests and property-based tests to ensure comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs

### Unit Testing

Unit tests will focus on:

1. **Endpoint Integration Tests**
   - Test health endpoint returns correct structure
   - Test predict endpoint with valid requests
   - Test metrics endpoint returns Prometheus format
   - Test error responses for invalid inputs

2. **Service Layer Tests**
   - Test ScreenshotProcessor with mock models
   - Test StatusChecker with various model states
   - Test MetricsCollector accumulation and formatting

3. **Edge Cases**
   - Empty image URLs list
   - Invalid app_name/language
   - conf_threshold boundary values (0.0, 1.0, -0.1, 1.1)
   - Model loading failures
   - Image download failures

4. **Error Handling Tests**
   - Model unavailable scenarios
   - Network failures
   - Invalid image formats
   - Orchestrator failures

### Property-Based Testing

Property tests will use **Hypothesis** (Python's property-based testing library) with minimum 100 iterations per test.

Each property test will:
- Generate random valid inputs
- Verify the property holds for all inputs
- Reference the design document property
- Use tag format: **Feature: chatcoach-api-refactor, Property {number}: {property_text}**

**Property Test Examples**:

```python
from hypothesis import given, strategies as st

@given(
    urls=st.lists(st.text(min_size=10), min_size=1, max_size=5),
    app_name=st.sampled_from(["whatsapp", "telegram", "discord"]),
    language=st.sampled_from(["en", "zh", "es"]),
    user_id=st.text(min_size=1)
)
def test_property_3_screenshot_analysis_completeness(
    urls, app_name, language, user_id
):
    """
    Feature: chatcoach-api-refactor, Property 3:
    For any valid predict request with image URLs, each URL should
    produce an ImageResult with a dialogs array
    """
    # Test implementation

@given(
    position=st.lists(
        st.floats(min_value=0.0, max_value=1.0),
        min_size=4,
        max_size=4
    )
)
def test_property_9_coordinate_normalization_bounds(position):
    """
    Feature: chatcoach-api-refactor, Property 9:
    For any position coordinate, all values should be in [0.0, 1.0]
    AND min_x ≤ max_x AND min_y ≤ max_y
    """
    # Test implementation
```

### Test Configuration

- Minimum 100 iterations per property test
- Use pytest for test execution
- Use pytest-asyncio for async tests
- Mock screenshotanalysis models for unit tests
- Use test fixtures for common setup

### Testing Tools

- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **Hypothesis**: Property-based testing
- **unittest.mock**: Mocking screenshotanalysis
- **httpx**: HTTP client for integration tests

## Implementation Notes

### Screenshotanalysis Integration

The screenshotanalysis library is installed in `core/screenshotanalysis/`. Integration approach:

1. **Import Strategy**:
   ```python
   try:
       import screenshotanalysis as AnalysisCore
       TextObjDet = AnalysisCore.text_det
       DocLayoutDet = AnalysisCore.layout_det
       EnTextRec = AnalysisCore.en_rec
       MODELS_AVAILABLE = True
   except ImportError:
       MODELS_AVAILABLE = False
   ```

2. **Lazy Loading**:
   - Models are loaded on first use
   - Loading failures set `ServerStatus.MODEL_UNAVAILABLE = True`
   - Health endpoint checks model status

3. **Model Management**:
   - Text detection: `TextObjDet.analyze_chat_screenshot(image)`
   - Layout detection: `DocLayoutDet.analyze_chat_screenshot(image)`
   - Text recognition: `EnTextRec.predict_text(text_image)`

### Configuration Management

Configuration will be loaded from:
1. `config.yaml` file (if exists)
2. Environment variables (override file config)
3. Default values (fallback)

```python
class ChatCoachConfig:
    @staticmethod
    def load_config() -> dict:
        """Load configuration from file and environment"""
        config = load_yaml("config.yaml")
        config.update(load_env_overrides())
        return config
    
    @staticmethod
    def get_app_names() -> list[str]:
        """Get supported app names from config"""
        return config.get("supported_apps", ["whatsapp", "telegram"])
    
    @staticmethod
    def get_languages() -> list[str]:
        """Get supported languages from config"""
        return config.get("supported_languages", ["en", "zh"])
```

### Logging Configuration

```python
def setup_logger(name: str, level: int, format_string: str):
    """Setup logger with specified configuration"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(format_string))
    logger.addHandler(handler)
    return logger

def configure_submodule_loggers(level: int, format_string: str):
    """Configure screenshotanalysis loggers"""
    for module in ["screenshotanalysis", "paddleocr"]:
        setup_logger(module, level, format_string)
```

### Orchestrator Integration

The predict endpoint will integrate with the existing Orchestrator:

```python
if request.reply and dialogs:
    # Format dialogs as conversation
    conversation = [
        {"speaker": d.speaker, "text": d.text}
        for d in all_dialogs
    ]
    
    # Call orchestrator
    try:
        reply_result = await orchestrator.generate_reply(
            user_id=request.user_id,
            conversation=conversation,
            language=request.language
        )
        if reply_result.success:
            suggested_replies = reply_result.replies
    except Exception as e:
        logger.error(f"Reply generation failed: {e}")
        # Continue without replies
```

### Migration Path

1. **Phase 1**: Implement new API structure
   - Create v1 router and endpoints
   - Implement ScreenshotProcessor service
   - Add configuration management

2. **Phase 2**: Integrate screenshotanalysis
   - Import and initialize models
   - Implement screenshot processing logic
   - Add error handling

3. **Phase 3**: Connect to Orchestrator
   - Integrate reply generation
   - Test end-to-end flow

4. **Phase 4**: Testing and validation
   - Write unit tests
   - Write property tests
   - Performance testing

5. **Phase 5**: Documentation and deployment
   - Update API documentation
   - Deploy to staging
   - Monitor and iterate
