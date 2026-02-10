# Changes Summary - Logging Improvements

## Date: 2026-02-09

## Changes Made

### 1. Removed LTR Embedding Marks from screenshot_parser.py

**File:** `app/services/screenshot_parser.py`

**Issue:** Unicode LTR embedding marks (`\u202A` and `\u202C`) were added to help with Arabic text display in Windows terminals, but they can cause display issues and are not necessary for the logging functionality.

**Change:** Removed the LTR embedding marks from the bubble text display in `_log_merge_step_conversation` method.

**Before:**
```python
display_text = f"\u202A{display_text}\u202C"  # LTR embedding
```

**After:**
```python
# No LTR embedding - text displays as-is
```

### 2. Removed Debug Marker from Log Output

**File:** `app/services/screenshot_parser.py`

**Issue:** The log output contained "*** NEW CODE VERSION ***" which was a temporary debug marker.

**Change:** Removed the debug marker from the log message.

**Before:**
```python
logger.info(
    f"[{session_id}] 🏁 RACE [{strategy}|{model}] *** NEW CODE VERSION *** Extracted {len(sorted_bubbles)} bubbles (sorted top→bottom):"
)
```

**After:**
```python
logger.info(
    f"[{session_id}] 🏁 RACE [{strategy}|{model}] Extracted {len(sorted_bubbles)} bubbles (sorted top→bottom):"
)
```

### 3. Added Debug Configuration Check to orchestrator.py

**File:** `app/services/orchestrator.py`

**Issue:** The `_log_merge_step_extraction` method in orchestrator was not checking the debug configuration before logging, which means it would always log regardless of the `DEBUG_LOG_MERGE_STEP_EXTRACTION` setting.

**Change:** Added debug configuration check at the beginning of the method.

**Added:**
```python
# Check if logging is enabled
from app.core.config import settings
if not settings.debug_config.log_merge_step_extraction:
    return
```

### 4. Updated Documentation

**File:** `docs/DEBUG_CONFIGURATION.md`

**Changes:**
- Added explanation of emoji markers (🏁 RACE vs 📊 FINAL)
- Added complete example output showing both race and final logs
- Added testing instructions using `test_logging_output.py` and `load_test.py`
- Added Windows terminal display troubleshooting section
- Clarified the difference between race process logs and final result logs

### 5. Created Test Script

**File:** `test_logging_output.py`

**Purpose:** Simple test script to verify merge_step logging is working correctly.

**Usage:**
```bash
# Start server
python main.py

# In another terminal
python test_logging_output.py
```

## Log Output Format

### Race Process Logs (from screenshot_parser.py)
```
INFO - [session] merge_step [multimodal|model] Participants: User='...', Target='...'
INFO - [session] 🏁 RACE [multimodal|model] Extracted 11 bubbles (sorted top→bottom):
INFO - [session] 🏁   [1] talker (left, y=100): 消息内容
INFO - [session] 🏁   [2] user (right, y=150): 回复内容
...
```

### Final Result Logs (from orchestrator.py)
```
INFO - [session] merge_step [multimodal|model] Participants: User='...', Target='...'
INFO - [session] 📊 FINAL [multimodal|model] Extracted 11 bubbles (sorted top→bottom):
INFO - [session] 📊   [1] talker (left, y=100): 消息内容
INFO - [session] 📊   [2] user (right, y=150): 回复内容
...
```

## Debug Configuration

All logging is controlled by environment variables in `.env`:

```env
# Wait for all models to complete (for comparison)
DEBUG_RACE_WAIT_ALL=false

# Enable/disable specific logging
DEBUG_LOG_MERGE_STEP_EXTRACTION=true
DEBUG_LOG_SCREENSHOT_PARSE=true
DEBUG_LOG_RACE_STRATEGY=true
DEBUG_LOG_LLM_CALLS=false
DEBUG_LOG_VALIDATION=false
```

## Testing

### Option 1: Using test_logging_output.py
```bash
python test_logging_output.py
```

### Option 2: Using load_test.py
```bash
python tests/load_test.py --url http://localhost:80 --image-url https://test-r2.zhizitech.org/test35.jpg --requests 1 --concurrent 1 --disable-cache --language zh
```

## Expected Behavior

### With DEBUG_RACE_WAIT_ALL=false (Production Mode)
- Only the first valid model's logs appear in race process
- Final result logs show the winning model
- Faster response time
- Lower token consumption

### With DEBUG_RACE_WAIT_ALL=true (Debug Mode)
- All models' logs appear in race process
- Can compare extraction quality between models
- Final result logs show the winning model
- Slower response time
- Higher token consumption

## Notes

1. **Emoji Display:** If emojis don't display correctly in Windows CMD/PowerShell, use Windows Terminal or configure UTF-8 encoding
2. **Log Volume:** With all debug logs enabled, output can be verbose. Use selectively in production
3. **Performance:** `DEBUG_RACE_WAIT_ALL=true` doubles API costs as it waits for both models
4. **Language Parameter:** load_test.py now supports `--language` parameter (e.g., `--language zh`, `--language ar`)

## Files Modified

1. `app/services/screenshot_parser.py` - Removed LTR marks and debug marker
2. `app/services/orchestrator.py` - Added debug configuration check
3. `docs/DEBUG_CONFIGURATION.md` - Updated documentation with examples and troubleshooting
4. `test_logging_output.py` - Created new test script

## Files Already Correct

1. `app/core/config.py` - DebugConfig class already implemented correctly
2. `.env` - Debug settings already configured correctly
3. `tests/load_test.py` - Language parameter already implemented correctly
