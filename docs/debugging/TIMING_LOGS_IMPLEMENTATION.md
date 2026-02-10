# Timing Logs Implementation Summary

## Overview

Implemented controlled timing logs for the ChatCoach API to enable performance monitoring without cluttering regular logs. The timing logs are integrated with the existing trace logging system and can be enabled/disabled via configuration.

## Changes Made

### 1. Configuration Changes

#### `app/core/config.py`
- Added `log_timing: bool = False` to `TraceConfig` class
- Enables/disables timing logs via `TRACE_LOG_TIMING` environment variable

#### `app/observability/trace_logger.py`
- Added `should_log_timing()` method to check if timing logs are enabled
- Returns `True` only when both `TRACE_ENABLED=true` and `TRACE_LOG_TIMING=true`

### 2. Predict Endpoint Changes

#### `app/api/v1/predict.py`

Replaced all `logger.info("[TIMING] ...")` calls with controlled `trace_logger.log_event()` calls:

**Main predict() function:**
- `predict_start`: Request received with metadata

**handle_text_qa() function:**
- `text_qa_start`: Text Q&A processing started
- `question_parsing`: Question text parsing
- `prompt_building`: Prompt construction
- `create_llm_adapter`: LLM adapter initialization
- `llm_call_start`: LLM API call started
- `llm_call_end`: LLM API call completed
- `metrics_recording`: Metrics collection
- `response_building`: Response object construction
- `text_qa_complete`: Total processing time

**handle_image() function:**
- `handle_image_start`: Image processing started
- `screenshot_start`: Screenshot analysis started (per image)
- `screenshot_end`: Screenshot analysis completed (per image)
- `scenario_analysis`: Scenario analysis duration
- `reply_generation`: Reply generation duration
- `handle_image_complete`: Total image processing time

### 3. Documentation

#### `docs/TIMING_LOGS.md`
- Comprehensive guide on using timing logs
- Configuration instructions
- Log format documentation
- Usage examples and analysis commands

#### `docs/TIMING_LOGS_IMPLEMENTATION.md`
- Technical implementation details
- List of all changes made

#### `.env.example`
- Added `TRACE_LOG_TIMING` environment variable with documentation

#### `examples/timing_logs_example.py`
- Example script showing how to enable and analyze timing logs
- Includes statistics calculation and bottleneck detection

## Key Features

### 1. Controlled Logging
- Timing logs only appear when explicitly enabled
- Requires both `TRACE_ENABLED=true` and `TRACE_LOG_TIMING=true`
- No performance impact when disabled

### 2. Structured Format
- All timing logs use JSON format in `logs/trace.jsonl`
- Consistent schema with `type`, `duration_ms`, `session_id`, etc.
- Easy to parse and analyze programmatically

### 3. No LLM Adapter Logging
- As requested, timing logs are NOT added to LLM adapter
- All timing logs are at the API endpoint level
- LLM adapter remains unchanged

### 4. Comprehensive Coverage
- Tracks all major processing steps
- Includes both duration and elapsed time
- Captures metadata (session_id, user_id, etc.)

## Usage

### Enable Timing Logs

```bash
# In .env file
TRACE_ENABLED=true
TRACE_LEVEL=debug
TRACE_LOG_TIMING=true
```

### Disable Timing Logs

```bash
# In .env file
TRACE_LOG_TIMING=false
# or
TRACE_ENABLED=false
```

### Analyze Logs

```bash
# View all timing logs
cat logs/trace.jsonl | grep duration_ms

# Find slow operations
cat logs/trace.jsonl | jq 'select(.duration_ms > 1000)'

# Calculate average screenshot analysis time
cat logs/trace.jsonl | jq 'select(.type == "screenshot_end") | .duration_ms' | awk '{sum+=$1; count++} END {print sum/count}'

# Use the example script
python examples/timing_logs_example.py
```

## Benefits

1. **Performance Monitoring**: Track processing time for each step
2. **Bottleneck Identification**: Find slow operations easily
3. **Optimization Validation**: Verify performance improvements
4. **Production Debugging**: Investigate slow requests without verbose logging
5. **Minimal Impact**: No overhead when disabled
6. **Structured Data**: Easy to parse and analyze

## Testing

To test the implementation:

1. Enable timing logs in `.env`:
   ```bash
   TRACE_ENABLED=true
   TRACE_LEVEL=debug
   TRACE_LOG_TIMING=true
   ```

2. Start the server:
   ```bash
   python main.py
   ```

3. Make API requests:
   ```bash
   curl -X POST http://localhost:8000/api/v1/ChatCoach/predict \
     -H "Content-Type: application/json" \
     -d '{"content": ["test"], "scene": 2, "user_id": "test"}'
   ```

4. Check timing logs:
   ```bash
   cat logs/trace.jsonl | grep duration_ms
   ```

## Migration Notes

- Old `[TIMING]` logs have been completely replaced
- No breaking changes to API or functionality
- Backward compatible (timing logs disabled by default)
- Existing trace logging functionality unchanged
