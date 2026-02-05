# Reply Generation Prompt Guide

## Available Versions

### v3.0-compact (Current)
- **File**: `prompts/versions/reply_generation_v3.0-compact.txt`
- **Status**: Production
- **Issue**: Sometimes LLM returns plain text instead of JSON
- **Success Rate**: ~98%

### v3.1-compact-strict-json (Recommended)
- **File**: `prompts/versions/reply_generation_v3.1-compact-strict-json.txt`
- **Status**: Ready for testing
- **Improvements**:
  - Stronger JSON format emphasis with ⚠️ CRITICAL section
  - Complete example with actual reply text
  - Explicit warning against plain text responses
  - Multiple "MUST" and "ONLY" keywords
- **Expected Success Rate**: 99.5%+

## How to Switch Prompts

### Option 1: Update Configuration

If using prompt manager:

```python
# In app/services/prompt_manager.py or config
REPLY_GENERATION_PROMPT_VERSION = "reply_generation_v3.1-compact-strict-json"
```

### Option 2: Direct File Update

Replace the content of the active prompt file with the new version.

### Option 3: A/B Testing

Run both versions in parallel and compare:

```python
# Test v3.0
result_v30 = await generate_reply(prompt_version="reply_generation_v3.0-compact")

# Test v3.1
result_v31 = await generate_reply(prompt_version="reply_generation_v3.1-compact-strict-json")

# Compare success rates
```

## Monitoring

### Check Plain Text Wrapping

```bash
# Count how often fallback is used
grep "LLM returned plain text instead of JSON" logs/app.log | wc -l

# See examples
grep "LLM returned plain text instead of JSON" logs/app.log | head -5
```

### Check Failed JSON Replies

```bash
# Count failed replies
ls logs-1/failed_json_replies/ | wc -l

# View recent failures
ls -lt logs-1/failed_json_replies/ | head -5
```

### Analyze by Model

```python
# In scripts/analyze_trace.py
# Filter by task_type="generation" and check for plain text responses
```

## Troubleshooting

### Issue: Still Getting Plain Text Responses

**Solutions**:
1. Verify you're using v3.1 prompt
2. Check if specific models are problematic
3. Consider adding system prompt emphasis
4. Try OpenAI JSON mode if using OpenAI models

### Issue: Wrapped Responses Have Low Quality

**Solutions**:
1. The wrapped response is just the plain text from LLM
2. This indicates prompt needs further strengthening
3. Consider model-specific prompts
4. May need to switch to a different model

### Issue: Too Many Warnings in Logs

**Solutions**:
1. If > 5% of requests trigger wrapping, prompt needs improvement
2. Check if specific conversation contexts trigger plain text
3. May need to add context-specific instructions

## Best Practices

### 1. Always Monitor After Changes

After switching prompts:
- Monitor for 24 hours
- Check success rate
- Review wrapped response quality
- Compare with baseline

### 2. Test with Different Scenarios

Test the prompt with:
- Different languages (en, zh)
- Different conversation contexts
- Different intimacy levels
- Different emotion states

### 3. Document Results

Keep track of:
- Success rate per prompt version
- Plain text wrapping frequency
- User feedback on reply quality
- Model-specific performance

## Quick Reference

| Metric | v3.0-compact | v3.1-compact-strict-json |
|--------|--------------|--------------------------|
| JSON Emphasis | Weak | Strong |
| Example Provided | No | Yes |
| Plain Text Warning | No | Yes |
| Expected Success | 98% | 99.5%+ |
| Fallback Needed | Yes | Rarely |

## Related Documentation

- `dev-docs/PLAIN_TEXT_JSON_SOLUTION.md` - Complete solution documentation
- `dev-docs/PROMPT_IMPROVEMENT_FOR_JSON.md` - Analysis and recommendations
- `scripts/test_plain_text_wrapping.py` - Test suite
- `prompts/metadata/reply_generation_v3.1-compact-strict-json.json` - Metadata

## Update History

- **2026-02-05**: Created guide for v3.1 prompt
