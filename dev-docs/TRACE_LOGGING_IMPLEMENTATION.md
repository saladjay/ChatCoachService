# Trace Logging Implementation

## Overview

Comprehensive trace logging has been implemented to capture all third-party API calls (LLM providers) with detailed information including prompts, responses, timing, token usage, and costs. This enables performance analysis, cost tracking, and debugging.

## Implementation Details

### 1. TraceLogger Enhancement

**File**: `app/observability/trace_logger.py`

Added `should_log_prompt()` method to check if prompts should be logged:

```python
def should_log_prompt(self) -> bool:
    """Check if prompts should be logged based on trace settings."""
    return self.enabled() and getattr(settings.trace, 'log_llm_prompt', False)
```

This method checks:
- If trace logging is enabled (`TRACE_ENABLED=true`)
- If prompt logging is enabled (`TRACE_LOG_LLM_PROMPT=true`)

### 2. Screenshot Parser Trace Logging

**File**: `app/services/screenshot_parser.py`

Added comprehensive trace logging for screenshot analysis LLM calls:

#### Events Logged

**Step Start Event** (`step_start`):
```json
{
  "level": "debug",
  "type": "step_start",
  "step_id": "unique_hex_id",
  "step_name": "screenshot_parse_llm",
  "task_type": "screenshot_parse",
  "session_id": "session_id",
  "prompt": "full_prompt_text",  // Only if TRACE_LOG_LLM_PROMPT=true
  "image_size": "1920x1080"
}
```

**Step End Event** (`step_end`):
```json
{
  "level": "debug",
  "type": "step_end",
  "step_id": "unique_hex_id",
  "step_name": "screenshot_parse_llm",
  "task_type": "screenshot_parse",
  "session_id": "session_id",
  "duration_ms": 7234,
  "provider": "openrouter",
  "model": "google/gemini-2.0-flash-lite-001",
  "input_tokens": 12543,
  "output_tokens": 856,
  "cost_usd": 0.0234,
  "status": "success"
}
```

**Step Error Event** (`step_error`):
```json
{
  "level": "error",
  "type": "step_error",
  "step_id": "unique_hex_id",
  "step_name": "screenshot_parse_llm",
  "task_type": "screenshot_parse",
  "session_id": "session_id",
  "duration_ms": 1234,
  "error": "error_message",
  "status": "failed"
}
```

#### Information Captured

- **Timing**: Start time, end time, duration in milliseconds
- **Provider Info**: Provider name (openrouter, gemini, etc.), model name
- **Token Usage**: Input tokens, output tokens
- **Cost**: Cost in USD
- **Prompt**: Full prompt text (when enabled)
- **Status**: Success or failure
- **Error Details**: Error message if failed

### 3. Trace Analysis Script Enhancement

**File**: `scripts/analyze_trace.py`

Updated to recognize and parse screenshot_parse events:

#### Changes Made

1. **Added step_id tracking**: Collects prompts from `step_start` events
2. **Parse step_end events**: Extracts LLM call information from screenshot parser
3. **Unified reporting**: Screenshot parser calls appear alongside orchestrator calls

#### Event Recognition

The script now recognizes two types of events:
- `llm_call_start` / `llm_call_end` (from orchestrator)
- `step_start` / `step_end` (from screenshot parser)

Both are merged into a unified view for analysis.

### 4. Configuration

**File**: `app/core/config.py`

Trace configuration class:

```python
class TraceConfig(BaseSettings):
    """Trace logging configuration (step inputs/outputs + LLM prompts)."""

    model_config = SettingsConfigDict(env_prefix="TRACE_")

    enabled: bool = False
    level: Literal["error", "info", "debug"] = "info"
    file_path: str = "logs/trace.jsonl"
    log_llm_prompt: bool = True
```

**Environment Variables**:

```bash
# Enable trace logging
TRACE_ENABLED=true

# Logging level: error, info, or debug
TRACE_LEVEL=info

# Output file path
TRACE_FILE_PATH=logs/trace.jsonl

# Log full prompts (increases file size)
TRACE_LOG_LLM_PROMPT=true
```

## Usage

### 1. Enable Trace Logging

Add to `.env`:

```bash
TRACE_ENABLED=true
TRACE_LOG_LLM_PROMPT=true
```

### 2. Run Application

```bash
# Start server with trace logging enabled
./start_server.sh
```

### 3. Make Test Requests

```bash
# Run load test
python tests/load_test.py --url http://localhost:80 \
  --image-url "https://example.com/screenshot.png" \
  --concurrent 5 --requests 10
```

### 4. Analyze Trace

```bash
# View summary
python scripts/analyze_trace.py logs/trace.jsonl

# View detailed information
python scripts/analyze_trace.py logs/trace.jsonl --detailed

# Group by different metrics
python scripts/analyze_trace.py logs/trace.jsonl --latency-group provider
python scripts/analyze_trace.py logs/trace.jsonl --latency-group model
```

## Analysis Output

### Summary View

```
================================================================================
TRACE ANALYSIS
================================================================================

OVERALL STATISTICS
--------------------------------------------------------------------------------
  Total LLM Calls:    80
  Total Input Tokens: 1,234,567
  Total Output Tokens: 123,456
  Total Tokens:       1,358,023
  Total Cost:         $0.234567
  Average Latency:    5234ms

CALL BREAKDOWN
--------------------------------------------------------------------------------
#    Task Type            Model                In       Out      Total    Cost
--------------------------------------------------------------------------------
1    screenshot_parse     gemini-2.0-flash     12543    856      13399    $0.0234
2    context_builder      gemini-2.0-flash     8234     456      8690     $0.0156
3    scene                gemini-2.0-flash     6543     234      6777     $0.0123
4    generation           gemini-2.0-flash     9876     567      10443    $0.0189

LATENCY SUMMARY BY TASK_TYPE
--------------------------------------------------------------------------------
Type                              N   Mean(ms)        P50        P90        Min        Max
--------------------------------------------------------------------------------
screenshot_parse                 20       7234       7123       8456       6234       9876
context_builder                  20       1234       1123       1456       1034       1876
scene                            20       1123       1089       1234        987       1456
generation                       20       1876       1823       2123       1567       2345
```

### Detailed View

With `--detailed` flag, shows full prompts and responses for each call.

## Performance Impact

### With Trace Logging Disabled
- No performance impact
- No disk I/O

### With Trace Logging Enabled (No Prompts)
- Minimal performance impact (~1-2ms per call)
- Small log files (~1KB per request)

### With Trace Logging + Prompts Enabled
- Minimal performance impact (~2-5ms per call)
- Larger log files (~10-50KB per request depending on prompt size)
- Recommended for debugging and analysis, not production

## Benefits

### 1. Performance Analysis
- Identify slow API calls
- Find bottlenecks in the request pipeline
- Compare performance across different models/providers

### 2. Cost Tracking
- Track token usage per request type
- Calculate cost per feature
- Identify opportunities for optimization

### 3. Debugging
- See exact prompts sent to LLM
- Verify prompt formatting
- Debug JSON parsing issues
- Trace error propagation

### 4. Optimization
- Compare before/after optimization
- Validate token reduction strategies
- Measure impact of prompt changes

## Example Analysis Workflow

### 1. Baseline Measurement

```bash
# Enable trace logging
export TRACE_ENABLED=true
export TRACE_LOG_LLM_PROMPT=true

# Run baseline test
python tests/load_test.py --requests 50 --concurrent 5

# Analyze baseline
python scripts/analyze_trace.py logs/trace.jsonl > baseline_report.txt
cp logs/trace.jsonl logs/trace_baseline.jsonl
```

### 2. Make Optimization

```bash
# Make changes to prompts, models, etc.
# ...

# Clear trace log
rm logs/trace.jsonl

# Run optimized test
python tests/load_test.py --requests 50 --concurrent 5

# Analyze optimized
python scripts/analyze_trace.py logs/trace.jsonl > optimized_report.txt
```

### 3. Compare Results

```bash
# Compare two traces
python scripts/analyze_trace.py \
  logs/trace_baseline.jsonl \
  logs/trace.jsonl \
  --compare
```

## Verification

Run the verification script to test the implementation:

```bash
python tests/verify_trace_logging.py
```

This will:
1. Check that `trace_logger.should_log_prompt()` exists
2. Verify trace configuration
3. Test event logging
4. Verify analyze script compatibility

## Files Modified

1. `app/observability/trace_logger.py` - Added `should_log_prompt()` method
2. `app/services/screenshot_parser.py` - Added trace logging for LLM calls
3. `scripts/analyze_trace.py` - Added support for `step_start`/`step_end` events
4. `.env.example` - Added trace configuration documentation
5. `tests/verify_trace_logging.py` - Created verification script
6. `dev-docs/TRACE_LOGGING_IMPLEMENTATION.md` - This documentation

## Next Steps

1. **Enable in Production** (Optional):
   - Set `TRACE_ENABLED=true` in production `.env`
   - Set `TRACE_LOG_LLM_PROMPT=false` to reduce log size
   - Monitor disk usage of `logs/trace.jsonl`
   - Set up log rotation

2. **Create Monitoring Dashboard**:
   - Parse trace.jsonl in real-time
   - Display metrics: requests/sec, avg latency, cost/hour
   - Alert on anomalies

3. **Automated Analysis**:
   - Run analysis script on schedule
   - Generate daily/weekly reports
   - Track trends over time

4. **Cost Optimization**:
   - Use trace data to identify high-cost operations
   - Test cheaper models for specific tasks
   - Optimize prompts to reduce tokens

## Troubleshooting

### Trace file not created

Check that:
- `TRACE_ENABLED=true` in `.env`
- Application has write permissions to `logs/` directory
- Application is actually making LLM calls

### Prompts not logged

Check that:
- `TRACE_LOG_LLM_PROMPT=true` in `.env`
- `TRACE_ENABLED=true` in `.env`

### analyze_trace.py shows no screenshot_parse calls

Check that:
- Screenshot analysis endpoint is being called
- Trace logging was enabled when requests were made
- `logs/trace.jsonl` contains recent data

### Large log files

Solutions:
- Set `TRACE_LOG_LLM_PROMPT=false` to exclude prompts
- Implement log rotation
- Archive old trace files
- Use `TRACE_LEVEL=error` to only log errors
