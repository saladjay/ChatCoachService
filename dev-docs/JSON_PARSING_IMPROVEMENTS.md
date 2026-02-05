# JSON Parsing Improvements

## Problem

LLM responses were failing to parse because they were wrapped in markdown code blocks:

```
```json
{"r": [...], "adv": "..."}
```
```

The code was trying to parse this directly with `json.loads()`, which failed with:
```
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

## Root Cause

Different LLM providers have different output habits:
- **OpenAI/GPT models**: Often wrap JSON in markdown code blocks for readability
- **Gemini models**: May include markdown formatting
- **Other models**: Varying behaviors

The code was not handling these markdown wrappers consistently across different parts of the application.

## Solution

### 1. Created Unified JSON Parser

Added `parse_json_with_markdown()` function in `app/api/v1/predict.py`:

```python
def parse_json_with_markdown(text: str) -> dict:
    """Parse JSON text that may be wrapped in markdown code blocks."""
```

This function handles:
- Plain JSON: `{"key": "value"}`
- Markdown JSON block: ` ```json\n{"key": "value"}\n``` `
- Markdown code block: ` ```\n{"key": "value"}\n``` `
- JSON with extra text: `Some text {"key": "value"} more text`

### 2. Updated All JSON Parsing Locations

**`app/api/v1/predict.py` - `_generate_reply()`**
- Replaced direct `json.loads()` with `parse_json_with_markdown()`
- Added better error logging with truncated text preview
- Improved error messages

**`app/services/reply_generator_impl.py` - `_expand_compact_result()`**
- Improved markdown code block handling
- Added proper error logging
- Better exception handling with fallback to original result

### 3. Improved Error Handling

All JSON parsing now:
- Logs the actual text that failed to parse (truncated to 200 chars)
- Provides specific error messages
- Has proper exception handling
- Falls back gracefully when parsing fails

## Code Flow

### Reply Generation Flow

```
User Request
    ↓
predict.py: _generate_reply()
    ↓
orchestrator.py: generate_reply()
    ↓
orchestrator.py: _generate_with_retry()
    ↓
reply_generator_impl.py: generate_reply()
    ↓
llm_adapter.py: call()
    ↓
LLM Provider (returns JSON, possibly with markdown)
    ↓
reply_generator_impl.py: _expand_compact_result()
    ├─ Remove markdown wrappers
    ├─ Parse JSON
    └─ Expand compact format
    ↓
orchestrator.py: returns GenerateReplyResponse
    ↓
predict.py: _generate_reply()
    ├─ parse_json_with_markdown()
    ├─ Extract replies
    └─ Return suggested_replies
```

## Testing

### Test Cases Handled

1. **Plain JSON**
   ```json
   {"replies": [...]}
   ```

2. **Markdown JSON Block**
   ```
   ```json
   {"replies": [...]}
   ```
   ```

3. **Markdown Code Block**
   ```
   ```
   {"replies": [...]}
   ```
   ```

4. **JSON with Extra Text**
   ```
   Here is the response: {"replies": [...]} Hope this helps!
   ```

5. **Nested Code Blocks**
   ```
   ```json
   {"r": [["text", null]], "adv": "advice"}
   ```
   ```

## Benefits

1. **Robustness**: Handles various LLM output formats
2. **Consistency**: Same parsing logic across the application
3. **Debugging**: Better error messages with actual failed text
4. **Maintainability**: Centralized parsing logic
5. **Fallback**: Graceful degradation when parsing fails

## Future Improvements

### Option 1: Improve Prompts

Add to prompts:
```
IMPORTANT: Return ONLY the raw JSON object. 
Do not use markdown code blocks or any formatting.
Your response should start with { and end with }.
```

### Option 2: Use JSON Mode

Some providers support JSON mode:
```python
llm_call = LLMCall(
    ...
    response_format={"type": "json_object"}  # OpenAI JSON mode
)
```

### Option 3: Post-Processing Pipeline

Create a more sophisticated post-processing pipeline:
1. Detect response format
2. Apply appropriate parser
3. Validate structure
4. Transform to expected format

## Related Files

- `app/api/v1/predict.py` - Main predict endpoint with `parse_json_with_markdown()`
- `app/services/reply_generator_impl.py` - Reply generator with `_expand_compact_result()`
- `app/services/orchestrator.py` - Orchestrator with `generate_reply()`
- `app/services/llm_adapter.py` - LLM adapter interface

## Monitoring

Watch for these log messages:

**Success:**
```
INFO - Reply generation successful: 3 replies
```

**Parse Failure:**
```
ERROR - Failed to parse reply text as JSON: ```json\n{"r": ...
```

**Fallback:**
```
WARNING - Failed to expand compact result: ... Returning original result.
```
