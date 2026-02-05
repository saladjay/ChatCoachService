# Trace Logging Quick Start Guide

## Quick Setup (30 seconds)

### 1. Enable Trace Logging

Add to `.env`:
```bash
TRACE_ENABLED=true
TRACE_LOG_LLM_PROMPT=true
```

### 2. Restart Server

```bash
./start_server.sh
```

### 3. Make a Test Request

```bash
python tests/load_test.py --url http://localhost:80 \
  --image-url "https://test-r2.zhizitech.org/test_discord_2.png" \
  --concurrent 5 --requests 10
```

### 4. Analyze Results

```bash
python scripts/analyze_trace.py logs/trace.jsonl
```

## What You'll See

### Summary Output

```
OVERALL STATISTICS
--------------------------------------------------------------------------------
  Total LLM Calls:    40
  Total Input Tokens: 523,456
  Total Output Tokens: 12,345
  Total Tokens:       535,801
  Total Cost:         $0.089234
  Average Latency:    3456ms

LATENCY SUMMARY BY TASK_TYPE
--------------------------------------------------------------------------------
Type                              N   Mean(ms)        P50        P90        Min        Max
--------------------------------------------------------------------------------
screenshot_parse                 10       7234       7123       8456       6234       9876
context_builder                  10       1234       1123       1456       1034       1876
scene                            10       1123       1089       1234        987       1456
generation                       10       1876       1823       2123       1567       2345
```

### Key Insights

- **screenshot_parse**: Screenshot analysis (vision API call)
  - Typically 6-9 seconds
  - Highest token usage (~12K input tokens)
  - Biggest bottleneck (51% of total time)

- **context_builder**: Dialog summarization
  - Typically 1-2 seconds
  - Moderate token usage (~8K input tokens)

- **scene**: Scene analysis
  - Typically 1-1.5 seconds
  - Lower token usage (~6K input tokens)

- **generation**: Reply generation
  - Typically 1.5-2.5 seconds
  - Moderate token usage (~9K input tokens)

## Common Commands

### View Summary
```bash
python scripts/analyze_trace.py logs/trace.jsonl
```

### View Detailed (with prompts)
```bash
python scripts/analyze_trace.py logs/trace.jsonl --detailed
```

### Group by Provider
```bash
python scripts/analyze_trace.py logs/trace.jsonl --latency-group provider
```

### Group by Model
```bash
python scripts/analyze_trace.py logs/trace.jsonl --latency-group model
```

### Compare Before/After
```bash
# Save baseline
cp logs/trace.jsonl logs/trace_baseline.jsonl

# Make changes, run tests, then compare
python scripts/analyze_trace.py \
  logs/trace_baseline.jsonl \
  logs/trace.jsonl \
  --compare
```

## Verification

Test that everything is working:

```bash
python tests/verify_trace_logging.py
```

Expected output:
```
✓ trace_logger.enabled() = True
✓ trace_logger.should_log_prompt() = True
✓ All trace_logger methods exist
✓ Trace logging is properly configured!
```

## Troubleshooting

### No trace file created?

Check:
1. Is `TRACE_ENABLED=true` in `.env`?
2. Did you restart the server after changing `.env`?
3. Did you make any API requests?

### No screenshot_parse in output?

Check:
1. Are you calling the screenshot analysis endpoint?
2. Was trace logging enabled when you made the request?
3. Is the trace file recent? (check timestamp)

### Prompts not showing in detailed view?

Check:
1. Is `TRACE_LOG_LLM_PROMPT=true` in `.env`?
2. Did you use `--detailed` flag?

## Performance Tips

### For Production

Use minimal logging:
```bash
TRACE_ENABLED=true
TRACE_LOG_LLM_PROMPT=false  # Don't log prompts
TRACE_LEVEL=info            # Only log major steps
```

### For Debugging

Use full logging:
```bash
TRACE_ENABLED=true
TRACE_LOG_LLM_PROMPT=true   # Log full prompts
TRACE_LEVEL=debug           # Log everything
```

### For Cost Analysis

Log without prompts:
```bash
TRACE_ENABLED=true
TRACE_LOG_LLM_PROMPT=false  # Smaller files
TRACE_LEVEL=info
```

## File Sizes

Typical trace file sizes per request:

- **No prompts**: ~1KB per request
- **With prompts**: ~10-50KB per request

For 1000 requests:
- **No prompts**: ~1MB
- **With prompts**: ~10-50MB

## Log Rotation

To prevent large files, rotate logs periodically:

```bash
# Archive old logs
mv logs/trace.jsonl logs/trace_$(date +%Y%m%d_%H%M%S).jsonl

# Or delete old logs
rm logs/trace.jsonl
```

## Integration with Load Testing

Run load test with trace logging:

```bash
# Clear old trace
rm logs/trace.jsonl

# Run test
python tests/load_test.py --url http://localhost:80 \
  --image-url "https://test-r2.zhizitech.org/test_discord_2.png" \
  --concurrent 10 --requests 50

# Analyze
python scripts/analyze_trace.py logs/trace.jsonl

# Save report
python scripts/analyze_trace.py logs/trace.jsonl > report_$(date +%Y%m%d).txt
```

## What Gets Logged

### For Each LLM Call

- **Timing**: Start time, end time, duration (ms)
- **Provider**: openrouter, gemini, dashscope, etc.
- **Model**: Full model name
- **Tokens**: Input tokens, output tokens, total
- **Cost**: Cost in USD
- **Prompt**: Full prompt text (if enabled)
- **Response**: Full response text (if enabled)
- **Status**: success or failed
- **Error**: Error message (if failed)

### For Screenshot Parser

- **Task Type**: `screenshot_parse`
- **Step Name**: `screenshot_parse_llm`
- **Image Size**: Width x Height
- **Session ID**: Request session ID

### For Orchestrator

- **Task Type**: `context_builder`, `scene`, `generation`
- **Prompt Version**: Version of prompt used
- **Caller Module**: Which module made the call
- **Caller Function**: Which function made the call

## Next Steps

1. **Run your first trace**: Follow the Quick Setup above
2. **Analyze results**: Look for bottlenecks and high costs
3. **Optimize**: Use insights to improve performance
4. **Compare**: Test changes and compare before/after

## More Information

See `dev-docs/TRACE_LOGGING_IMPLEMENTATION.md` for complete documentation.
