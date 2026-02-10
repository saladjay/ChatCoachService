# Result Logging Truncation Issue

## Problem

When logging `result.results` in the predict endpoint, the text content gets truncated in the logs. This happens because:

1. Python's logging module has practical limits on message length
2. The `ImageResult` objects can contain very long text content (e.g., full articles, long responses)
3. String representation of large objects gets truncated by the logging system

Example of truncated output:
```
2026-02-10 16:36:37,429 - app.api.v1.predict - INFO - result: [ImageResult(content='https://...', dialogs=[...], scenario='{"current_scenario": "collaborative support session"...')]"text": "### Effective Ways to Research for Your Writing\n\nResearch is a crucial pillar of successful writing...**Tip**
```

## Solution

### Default Behavior (Production)
By default, only essential information is logged to avoid log bloat:
- Number of dialogs extracted
- Scenario preview (first 100 characters)
- Content URL

Example:
```
2026-02-10 16:36:37,429 - app.api.v1.predict - INFO - result[0]: 3 dialogs, scenario: {"current_scenario": "collaborative support session", "recommended_scenario": "SAFE"...
```

### Debug Mode (Development)
When you need to see the full content for debugging, enable the debug flag:

```bash
# In .env file
DEBUG_LOG_FULL_RESULT_CONTENT=true
```

Or set the environment variable:
```bash
export DEBUG_LOG_FULL_RESULT_CONTENT=true
```

This will log:
- Full content URL
- Complete scenario JSON
- All dialogs with full text (with preview for very long messages)

## Configuration

The logging behavior is controlled by `DebugConfig.log_full_result_content` in `app/core/config.py`:

```python
class DebugConfig(BaseSettings):
    log_full_result_content: bool = False  # Log full result content including long text
```

## Best Practices

1. **Production**: Keep `log_full_result_content=False` to avoid log bloat
2. **Development**: Enable when debugging specific issues with content extraction
3. **Monitoring**: Use the summary logs to track dialog counts and scenario types
4. **Debugging**: Enable full logging temporarily when investigating content issues

## Related Files

- `app/api/v1/predict.py` - Predict endpoint with logging logic
- `app/core/config.py` - Debug configuration
- `app/models/v1_api.py` - ImageResult model definition
