# Task 3: Screenshot Processor Service Implementation

## Summary

Successfully implemented the Screenshot Processor service (`app/services/screenshot_processor.py`) that integrates the screenshotanalysis library to perform OCR and layout detection on chat screenshots.

## Completed Sub-tasks

### 3.1 Create `app/services/screenshot_processor.py`
- ✅ Created the main service file with complete implementation
- ✅ Imported screenshotanalysis models (text_det, layout_det, en_rec)
- ✅ Implemented lazy model loading with error handling
- ✅ Implemented image loading from URLs using httpx
- ✅ Implemented image loading from base64 data
- ✅ Added proper error handling with custom exceptions

### 3.2 Implement text and layout detection
- ✅ Implemented `_detect_text_and_layout()` method
- ✅ Calls text detection analyzer (PP-OCRv5_server_det)
- ✅ Calls layout detection analyzer (PP-DocLayoutV2)
- ✅ Handles detection failures with InferenceError
- ✅ Returns structured results with padding and image size

### 3.3 Implement text extraction and speaker identification
- ✅ Implemented `_extract_text_from_box()` for OCR
- ✅ Implemented `_extract_nickname()` using nickname extractor
- ✅ Implemented `_identify_speaker()` to determine speaker (self vs other)
- ✅ Uses adaptive detection with speaker attributes when available
- ✅ Falls back to position-based heuristics

### 3.4 Implement coordinate normalization and message grouping
- ✅ Implemented `_normalize_coordinates()` to convert pixels to percentages (0.0-1.0)
- ✅ Adjusts for image padding
- ✅ Ensures coordinates are within valid range
- ✅ Implemented message grouping logic in `_extract_and_group_messages()`
- ✅ Groups consecutive messages by same speaker
- ✅ Formats as DialogItem models

## Key Features

### Error Handling
- **ModelUnavailableError**: Raised when screenshotanalysis models cannot be loaded
- **ImageLoadError**: Raised when image loading fails (HTTP errors, invalid format)
- **InferenceError**: Raised when model inference fails

### Lazy Loading
- Models are loaded on first use via `_load_models()`
- Prevents unnecessary initialization overhead
- Checks if models are already loaded before reloading

### Image Loading
- Supports loading from URLs (async with httpx)
- Supports loading from base64 encoded data
- Automatic RGB conversion for RGBA and other formats
- Proper error handling for network and format issues

### Text Detection & Layout Detection
- Uses PP-OCRv5_server_det for text detection
- Uses PP-DocLayoutV2 for layout detection
- Returns structured results with padding and image size
- Comprehensive error handling

### Text Extraction & Speaker Identification
- OCR text extraction from detected boxes
- Nickname extraction using smart extractor
- Speaker identification using adaptive detection
- Fallback to position-based heuristics

### Coordinate Normalization
- Converts pixel coordinates to percentages (0.0-1.0)
- Adjusts for image padding
- Ensures coordinates are within valid bounds
- Format: [min_x, min_y, max_x, max_y]

### Message Grouping
- Groups consecutive messages from same speaker
- Combines text from grouped messages
- Maintains position information
- Returns structured DialogItem objects

## Requirements Satisfied

- ✅ 4.1: Import screenshotanalysis models
- ✅ 4.2: Load images from URLs or base64 data
- ✅ 4.3: Perform text detection analysis
- ✅ 4.4: Perform layout detection analysis
- ✅ 4.5: Extract text from detected boxes using OCR
- ✅ 4.6: Identify chat message speakers (self vs other)
- ✅ 4.7: Extract nickname information
- ✅ 4.8: Return normalized position coordinates (0.0-1.0)
- ✅ 4.9: Group consecutive messages by same speaker
- ✅ 4.10: Raise model unavailable error on loading failure
- ✅ 4.11: Raise image load error on loading failure
- ✅ 4.12: Raise inference error on inference failure

## API Overview

### Main Method
```python
async def process_screenshot(
    self,
    image_url: str,
    app_type: str,
    conf_threshold: Optional[float] = None
) -> ImageResult
```

### Internal Methods
- `_load_models()`: Lazy load screenshotanalysis models
- `_load_image_from_url()`: Load image from URL
- `_load_image_from_base64()`: Load image from base64
- `_detect_text_and_layout()`: Perform text and layout detection
- `_extract_and_group_messages()`: Extract text and group by speaker
- `_extract_text_from_box()`: OCR text extraction
- `_extract_nickname()`: Extract nickname from screenshot
- `_identify_speaker()`: Identify message speaker
- `_normalize_coordinates()`: Normalize coordinates to percentages

## Testing

Basic import test passed successfully:
```bash
python -c "from app.services.screenshot_processor import ScreenshotProcessor; ..."
# Output: ScreenshotProcessor imported successfully
```

## Next Steps

The following optional test tasks are available:
- Task 3.5: Write property test for coordinate normalization
- Task 3.6: Write property test for speaker identification
- Task 3.7: Write property test for message grouping
- Task 3.8: Write unit tests for Screenshot Processor

## Notes

- The implementation uses the screenshotanalysis library from `core/screenshotanalysis/`
- Models are loaded lazily to avoid initialization overhead
- Comprehensive error handling ensures graceful failure modes
- The service integrates with existing ChatMessageProcessor for advanced processing
- Adaptive detection is used when available for better speaker identification
