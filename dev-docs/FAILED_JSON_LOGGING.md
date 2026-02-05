# Failed JSON Reply Logging

## Overview

When LLM-generated replies fail to parse as JSON, this feature logs the raw response text to files for analysis. This helps identify patterns in parsing failures and improve prompt engineering.

## Configuration

### Enable Logging

Edit `.env` file:

```bash
# Enable failed JSON reply logging
LOG_FAILED_JSON_REPLIES=true

# Disable logging (default)
LOG_FAILED_JSON_REPLIES=false
```

**Default**: `false` (logging disabled)

## Behavior

### When Enabled (LOG_FAILED_JSON_REPLIES=true)

When a reply fails to parse as JSON:

1. **Log to File**: Save complete reply text to `logs/failed_json_replies/`
2. **Include Metadata**: Timestamp, session_id, error message
3. **Continue Processing**: Error is still raised, but data is preserved
4. **Console Log**: Info message with filename

**File Format**:
```
logs/failed_json_replies/failed_reply_20260205_143022_123456_abc12345.json
```

**File Content**:
```json
{
  "timestamp": "2026-02-05T14:30:22.123456",
  "session_id": "abc12345-1234-5678-90ab-cdef12345678",
  "error": "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)",
  "reply_text": "{replies: [{text: 'Hello'}]}",
  "reply_length": 28
}
```

### When Disabled (LOG_FAILED_JSON_REPLIES=false)

- No files are created
- Only console error log (truncated to 200 chars)
- Normal error handling continues

## Use Cases

### 1. Debugging JSON Parsing Issues

**Problem**: 40% of requests fail with "Failed to parse reply text as JSON"

**Solution**:
```bash
# Enable logging
LOG_FAILED_JSON_REPLIES=true

# Run load test
python tests/load_test.py --concurrent 10 --requests 50

# Analyze failures
ls -lh logs/failed_json_replies/
cat logs/failed_json_replies/failed_reply_*.json
```

### 2. Improving Prompt Engineering

**Workflow**:
1. Enable logging during testing
2. Collect failed cases
3. Analyze common patterns:
   - Missing quotes around keys
   - Extra text before/after JSON
   - Incomplete JSON structures
   - Wrong format (array vs object)
4. Update prompts to address patterns
5. Re-test and verify improvement

### 3. Model Comparison

Compare JSON parsing reliability across different models:

```bash
# Test with Model A
LLM_DEFAULT_MODEL=google/gemini-2.0-flash-lite-001
LOG_FAILED_JSON_REPLIES=true
python tests/load_test.py --requests 100

# Count failures
ls logs/failed_json_replies/ | wc -l

# Test with Model B
LLM_DEFAULT_MODEL=google/gemini-2.5-flash
rm -rf logs/failed_json_replies/*
python tests/load_test.py --requests 100

# Compare failure rates
```

## Log File Management

### Directory Structure

```
logs/
└── failed_json_replies/
    ├── failed_reply_20260205_143022_123456_abc12345.json
    ├── failed_reply_20260205_143023_234567_def67890.json
    └── ...
```

### Cleanup

Logs are not automatically cleaned up. Manage manually:

```bash
# View log size
du -sh logs/failed_json_replies/

# Delete old logs (older than 7 days)
find logs/failed_json_replies/ -name "*.json" -mtime +7 -delete

# Delete all logs
rm -rf logs/failed_json_replies/*
```

### Disk Space Considerations

- Each log file: ~1-10 KB (depends on reply length)
- 100 failures: ~500 KB
- 1000 failures: ~5 MB

**Recommendation**: Enable only during debugging/testing, disable in production.

## Analysis Tools

### Count Failures by Error Type

```bash
# Extract error messages
jq -r '.error' logs/failed_json_replies/*.json | sort | uniq -c | sort -rn
```

Output:
```
  25 Expecting property name enclosed in double quotes: line 1 column 2
  10 Expecting ',' delimiter: line 3 column 5
   5 Unterminated string starting at: line 2 column 10
```

### Find Common Patterns

```bash
# Extract first 100 chars of each failed reply
jq -r '.reply_text[:100]' logs/failed_json_replies/*.json
```

### View Longest Failures

```bash
# Sort by reply length
jq -r '"\(.reply_length) \(.timestamp)"' logs/failed_json_replies/*.json | sort -rn | head -10
```

## Implementation Details

### Code Location

**Configuration**: `app/core/config.py`
```python
class AppConfig(BaseSettings):
    log_failed_json_replies: bool = False
```

**Logging Function**: `app/api/v1/predict.py`
```python
def _log_failed_json_reply(reply_text: str, session_id: str, error_msg: str):
    """Log failed JSON reply to file for analysis."""
    log_dir = Path("logs/failed_json_replies")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = log_dir / f"failed_reply_{timestamp}_{session_id[:8]}.json"
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "error": error_msg,
        "reply_text": reply_text,
        "reply_length": len(reply_text),
    }
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, indent=2, ensure_ascii=False)
```

**Usage**: `app/api/v1/predict.py`
```python
except json.JSONDecodeError as exc:
    logger.error(f"Failed to parse reply text as JSON: {reply_text[:200]}")
    
    # Log full failed JSON to file if enabled
    if settings.log_failed_json_replies:
        _log_failed_json_reply(reply_text, session_id, str(exc))
    
    raise ValueError(f"Failed to parse reply text as JSON: {str(exc)}")
```

## Performance Impact

- **Minimal**: Only writes to disk on failures
- **No impact on success path**: Zero overhead for successful requests
- **Async-safe**: File I/O is synchronous but fast (< 1ms per write)

## Security Considerations

### Sensitive Data

Log files may contain:
- User conversation content
- Generated replies
- Session IDs

**Recommendations**:
1. Restrict file permissions: `chmod 600 logs/failed_json_replies/*.json`
2. Add to `.gitignore`: `logs/`
3. Exclude from backups if sensitive
4. Delete after analysis

### Log Rotation

Not implemented. Consider external tools:
- `logrotate` (Linux)
- Scheduled cleanup scripts
- Log aggregation services (ELK, Splunk)

## Troubleshooting

### Issue: No logs created despite failures

**Check**:
1. Configuration: `LOG_FAILED_JSON_REPLIES=true` in `.env`
2. Permissions: Write access to `logs/` directory
3. Disk space: Sufficient space available

**Verify**:
```bash
python -c "from app.core.config import settings; print(settings.log_failed_json_replies)"
```

### Issue: Too many log files

**Solution**: Implement cleanup script

```bash
#!/bin/bash
# cleanup_failed_logs.sh
find logs/failed_json_replies/ -name "*.json" -mtime +7 -delete
```

Add to cron:
```bash
# Run daily at 2 AM
0 2 * * * /path/to/cleanup_failed_logs.sh
```

## Related Features

- [JSON Parsing Improvements](JSON_PARSING_IMPROVEMENTS.md) - Enhanced JSON parsing with markdown support
- [Intimacy Check Configuration](INTIMACY_CHECK_CONFIG.md) - Feature flag for intimacy validation
- [Cache Fix](CACHE_FIX_DUPLICATE_ANALYSIS.md) - Cache optimization

## Example Workflow

### Debugging High Failure Rate

```bash
# 1. Enable logging
echo "LOG_FAILED_JSON_REPLIES=true" >> .env

# 2. Restart server
./start_server.sh

# 3. Run load test
python tests/load_test.py --concurrent 10 --requests 100

# 4. Check results
echo "Total failures: $(ls logs/failed_json_replies/ | wc -l)"

# 5. Analyze patterns
echo "Error types:"
jq -r '.error' logs/failed_json_replies/*.json | sort | uniq -c

# 6. View sample failures
head -n 20 logs/failed_json_replies/failed_reply_*.json

# 7. Fix prompts based on patterns

# 8. Clean up and re-test
rm -rf logs/failed_json_replies/*
python tests/load_test.py --concurrent 10 --requests 100

# 9. Compare results
echo "New failure count: $(ls logs/failed_json_replies/ | wc -l)"

# 10. Disable logging when done
sed -i 's/LOG_FAILED_JSON_REPLIES=true/LOG_FAILED_JSON_REPLIES=false/' .env
```
