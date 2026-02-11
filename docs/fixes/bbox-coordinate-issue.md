# Bounding Box Coordinate Shrinking Issue

## Problem

User reported that bounding boxes in annotated images (`test29-31-annotated1.jpg`, `test29-31-annotated2.jpg`) appear smaller than the actual dialog bubbles in the original image (`test29-31.jpg`).

## Root Cause Analysis

### 1. Image Dimensions
- Original image: **574 x 1279 pixels**

### 2. Logged Coordinates
From the logs:
```
[1] talker(left) OK bbox=[0,160,300,250]
[2] user(right) OK bbox=[300,160,600,300]
```

### 3. The Problem
The bbox x2 coordinate (600) **exceeds the image width** (574), which is impossible if these were true pixel coordinates.

### 4. Coordinate Scale Mismatch

The LLM is returning coordinates in a **normalized scale** (0-1000 range), but the code was treating them as pixel coordinates without validation.

If we interpret the coordinates as normalized (0-1000 range):
- `bbox=[0,160,300,250]` → normalized: `[0.0, 0.16, 0.3, 0.25]`
- `bbox=[300,160,600,300]` → normalized: `[0.3, 0.16, 0.6, 0.3]`

Converting to actual pixels (574x1279):
- Bbox 1: `[0, 204.6, 172.2, 319.8]` pixels
- Bbox 2: `[172.2, 204.6, 344.4, 383.7]` pixels

## Code Flow Analysis

### Merge Step Prompt
From `prompts/active/merge_step.txt`:
```
For each bubble:
- bbox:{x1,y1,x2,y2} (original pixels)
```

The prompt **explicitly asks for pixel coordinates**, but the LLM is not following this instruction consistently.

### Coordinate Extraction (Before Fix)
In `app/services/merge_step_adapter.py` (lines 85-89):
```python
# Extract bbox coordinates
x1 = float(bbox_data.get("x1", 0))
y1 = float(bbox_data.get("y1", 0))
x2 = float(bbox_data.get("x2", 0))
y2 = float(bbox_data.get("y2", 0))
```

The coordinates were extracted **as-is** without any validation or normalization.

### Old vs New Flow

**Old Flow (ScreenshotParserService):**
- Uses `ResultNormalizer.normalize()`
- Normalizes coordinates to 0-1 range: `x1 / image_width`
- Located in `app/services/result_normalizer.py` (lines 290-294)

**New Flow (Orchestrator with merge_step):**
- Uses `MergeStepAdapter.to_parsed_screenshot_data()`
- **Was missing normalization** - coordinates used as-is
- Located in `app/services/merge_step_adapter.py`

## Solution Implemented

Added automatic coordinate scale detection and normalization in `MergeStepAdapter.to_parsed_screenshot_data()`:

### Two-Pass Algorithm

**Pass 1: Detect coordinate scale**
```python
# Check all bubbles to determine scale
for bubble_data in bubbles_data:
    bbox_data = bubble_data.get("bbox", {})
    x1, y1, x2, y2 = extract_coords(bbox_data)
    max_x = max(max_x, x1, x2)
    max_y = max(max_y, y1, y2)

# Determine scale
if all_coords <= 1.0:
    scale = "normalized_0_1"
elif max_x > image_width or max_y > image_height:
    scale = "normalized_0_1000"
else:
    scale = "pixels"
```

**Pass 2: Apply normalization**
```python
for bubble in bubbles:
    x1, y1, x2, y2 = extract_coords(bubble)
    
    if scale == "normalized_0_1":
        x1 *= image_width
        y1 *= image_height
        x2 *= image_width
        y2 *= image_height
    elif scale == "normalized_0_1000":
        x1 = (x1 / 1000.0) * image_width
        y1 = (y1 / 1000.0) * image_height
        x2 = (x2 / 1000.0) * image_width
        y2 = (y2 / 1000.0) * image_height
```

### Benefits

1. **Backward compatible** - handles pixel, 0-1, and 0-1000 coordinate scales
2. **Automatic detection** - no manual configuration needed
3. **Consistent normalization** - all bubbles in a batch use the same scale
4. **Clear logging** - warns when normalization is applied
5. **Validation** - checks for invalid coordinates after normalization

## Testing

Created `test_bbox_normalization.py` with three test cases:

1. **Coordinates in 0-1000 range** (the reported issue)
   - Input: `bbox=[0,160,300,250]` and `bbox=[300,160,600,300]`
   - Output: `bbox=[0.0,204.6,172.2,319.8]` and `bbox=[172.2,204.6,344.4,383.7]`
   - ✓ All coordinates within image bounds

2. **Coordinates in 0-1 range**
   - Input: `bbox=[0.0,0.16,0.3,0.25]`
   - Output: `bbox=[0.0,204.6,172.2,319.8]`
   - ✓ Correctly converted to pixels

3. **Coordinates already in pixels**
   - Input: `bbox=[10,200,200,400]`
   - Output: `bbox=[10.0,200.0,200.0,400.0]`
   - ✓ Unchanged (no normalization needed)

All tests pass successfully.

## Impact

- **Fixed**: Bounding boxes will now be correctly sized in annotated images
- **No breaking changes**: Existing code continues to work
- **Better error detection**: Invalid coordinates are logged as warnings
- **Improved robustness**: Handles multiple coordinate formats from different LLM providers

## Related Files

- `app/services/merge_step_adapter.py` - **MODIFIED** - Added coordinate normalization
- `test_bbox_normalization.py` - **NEW** - Test suite for coordinate normalization
- `docs/fixes/bbox-coordinate-issue.md` - **NEW** - This document
- `app/services/orchestrator.py` - Uses merge_step_adapter
- `app/services/result_normalizer.py` - Old normalization logic (reference)
- `prompts/active/merge_step.txt` - LLM prompt

## Status

✅ **FIXED** - Implemented and tested on 2026-02-10
