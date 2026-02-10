# Timing Logs Quick Start Guide

## Enable Timing Logs (3 Steps)

### 1. Edit `.env` file

```bash
TRACE_ENABLED=true
TRACE_LEVEL=debug
TRACE_LOG_TIMING=true
```

### 2. Restart the server

```bash
python main.py
```

### 3. View logs

```bash
# View all timing logs
tail -f logs/trace.jsonl | grep duration_ms

# Or use jq for better formatting
tail -f logs/trace.jsonl | jq 'select(.duration_ms)'
```

## What You'll See

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

## Common Timing Events

| Event Type | Description |
|------------|-------------|
| `predict_start` | Request received |
| `screenshot_start` | Screenshot analysis started |
| `screenshot_end` | Screenshot analysis completed |
| `scenario_analysis` | Scenario analysis duration |
| `reply_generation` | Reply generation duration |
| `handle_image_complete` | Total image processing time |
| `text_qa_complete` | Total Q&A processing time |

## Quick Analysis Commands

```bash
# Find slow operations (>1000ms)
cat logs/trace.jsonl | jq 'select(.duration_ms > 1000)'

# Average screenshot analysis time
cat logs/trace.jsonl | jq 'select(.type == "screenshot_end") | .duration_ms' | awk '{sum+=$1; count++} END {print sum/count}'

# Count events by type
cat logs/trace.jsonl | jq -r '.type' | sort | uniq -c

# View last 10 timing events
tail -10 logs/trace.jsonl | jq 'select(.duration_ms)'
```

## Disable Timing Logs

```bash
# In .env file
TRACE_LOG_TIMING=false
```

## Need More Help?

- Full documentation: `docs/TIMING_LOGS.md`
- Implementation details: `docs/TIMING_LOGS_IMPLEMENTATION.md`
- Example script: `examples/timing_logs_example.py`
