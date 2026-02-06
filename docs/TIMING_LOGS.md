# Timing Logs Configuration

## Overview

The timing logs feature provides detailed performance monitoring for the ChatCoach API. It tracks the duration of each processing step to help identify performance bottlenecks.

## Configuration

Timing logs are controlled through the trace configuration system. To enable timing logs:

### Environment Variables

Add to your `.env` file:

```bash
# Enable trace logging (required)
TRACE_ENABLED=true

# Set trace level (debug recommended for timing logs)
TRACE_LEVEL=debug

# Enable timing logs
TRACE_LOG_TIMING=true

# Optional: Specify trace log file path
TRACE_FILE_PATH=logs/trace.jsonl
```

### YAML Configuration

Add to your `config.yaml` file:

```yaml
# Not directly configurable via YAML - use environment variables
```

## What Gets Logged

When `TRACE_LOG_TIMING=true`, the following timing information is logged:

### Predict Endpoint
- **predict_start**: Request received
- **question_parsing**: Text parsing for Q&A
- **prompt_building**: Prompt construction
- **create_llm_adapter**: LLM adapter initialization
- **llm_call_start/end**: LLM API calls
- **metrics_recording**: Metrics collection
- **response_building**: Response object construction
- **text_qa_complete**: Total Q&A processing time

### Handle Image Function
- **handle_image_start**: Image processing started
- **screenshot_start/end**: Screenshot analysis (per image)
- **scenario_analysis**: Scenario analysis duration
- **reply_generation**: Reply generation duration
- **handle_image_complete**: Total image processing time

## Log Format

Timing logs are written in JSONL format to `logs/trace.jsonl`:

```json
{
  "level": "debug",
  "type": "screenshot_end",
  "task_type": "screenshot_parse",
  "url": "https://example.com/image.jpg",
  "session_id": "abc123",
  "user_id": "user456",
  "duration_ms": 1234,
  "ts": 1707234567.890
}
```

## Usage Examples

### Enable Timing Logs for Development

```bash
# In .env file
TRACE_ENABLED=true
TRACE_LEVEL=debug
TRACE_LOG_TIMING=true
```

### Disable Timing Logs for Production

```bash
# In .env file
TRACE_ENABLED=false
# or
TRACE_LOG_TIMING=false
```

### Analyze Performance

```bash
# View timing logs
cat logs/trace.jsonl | grep "duration_ms"

# Find slow operations (>1000ms)
cat logs/trace.jsonl | jq 'select(.duration_ms > 1000)'

# Calculate average screenshot analysis time
cat logs/trace.jsonl | jq 'select(.type == "screenshot_end") | .duration_ms' | awk '{sum+=$1; count++} END {print sum/count}'
```

## Benefits

1. **Performance Monitoring**: Track processing time for each step
2. **Bottleneck Identification**: Find slow operations
3. **Optimization Validation**: Verify performance improvements
4. **Production Debugging**: Investigate slow requests without verbose logging

## Notes

- Timing logs require `TRACE_ENABLED=true` to work
- Logs are written to `logs/trace.jsonl` by default
- Use `TRACE_LEVEL=debug` to see all timing events
- Timing logs have minimal performance impact
- No timing logs are written to LLM adapter (as requested)
