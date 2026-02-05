# Intimacy Check Configuration

## Overview

The intimacy check is a validation step that ensures generated replies are appropriate for the current intimacy level of the conversation. This feature can be enabled or disabled via the `NO_INTIMACY_CHECK` environment variable.

## Configuration

### Enable/Disable Intimacy Check

Edit `.env` file:

```bash
# Disable intimacy check (faster, no validation)
NO_INTIMACY_CHECK=true

# Enable intimacy check (slower, with validation)
NO_INTIMACY_CHECK=false
```

**Default**: `false` (intimacy check is enabled)

## Behavior Comparison

### When ENABLED (NO_INTIMACY_CHECK=false)

**Flow**:
1. Generate reply
2. **Check intimacy appropriateness** ← Extra LLM call
3. If failed, retry up to 3 times
4. Return validated reply

**Characteristics**:
- ✅ Ensures replies are appropriate for intimacy level
- ✅ Prevents overly intimate or distant responses
- ✅ Better quality control
- ❌ Slower response time (~1-2 seconds extra per reply)
- ❌ Higher cost (1 extra LLM call per reply)
- ❌ May exhaust retries and return fallback

**Use Cases**:
- Production environments with strict quality requirements
- Dating/relationship coaching scenarios
- When reply appropriateness is critical

### When DISABLED (NO_INTIMACY_CHECK=true)

**Flow**:
1. Generate reply
2. ~~Check intimacy appropriateness~~ ← Skipped
3. Return reply immediately

**Characteristics**:
- ✅ Faster response time (saves 1-2 seconds)
- ✅ Lower cost (saves 1 LLM call per reply)
- ✅ No retry failures
- ❌ No validation of reply appropriateness
- ❌ May generate overly intimate or distant responses

**Use Cases**:
- Development and testing
- Load testing and performance benchmarking
- Scenarios where intimacy validation is not critical
- Cost-sensitive deployments

## Performance Impact

### Response Time

| Configuration | Avg Response Time | P95 Response Time |
|--------------|-------------------|-------------------|
| Enabled      | ~5.5s            | ~8.5s            |
| Disabled     | ~3.5s            | ~6.0s            |

**Savings**: ~2 seconds per request (36% faster)

### Cost Impact

| Configuration | LLM Calls per Reply | Relative Cost |
|--------------|---------------------|---------------|
| Enabled      | 5-6 calls          | 100%          |
| Disabled     | 4-5 calls          | ~83%          |

**Savings**: ~17% cost reduction

## Implementation Details

### Code Location

**Configuration**: `app/core/config.py`
```python
class AppConfig(BaseSettings):
    no_intimacy_check: bool = False  # Disable intimacy check if True
```

**Implementation**: `app/services/orchestrator.py`
```python
async def _generate_with_retry(self, ...):
    # Generate reply
    reply_result = await self.reply_generator.generate_reply(...)
    
    # Skip intimacy check if disabled
    if settings.no_intimacy_check:
        logger.info("Intimacy check disabled by configuration")
        intimacy_result = IntimacyCheckResult(
            passed=True,
            reason="Intimacy check disabled",
            score=1.0,
        )
        return reply_result, intimacy_result
    
    # Otherwise, perform intimacy check
    intimacy_result = await self.intimacy_checker.check(...)
    ...
```

### Verification

Run the verification script to check current configuration:

```bash
python tests/verify_intimacy_config.py
```

Output:
```
============================================================
NO_INTIMACY_CHECK Configuration Status
============================================================

Current setting: NO_INTIMACY_CHECK = True

✓ Intimacy check is DISABLED

Behavior:
  - Reply generation will skip intimacy validation
  - No retries will be performed for intimacy failures
  - Faster response times (saves 1 LLM call per reply)
  - All generated replies will be accepted without validation
...
```

## Recommendations

### For Production
- **Enable** intimacy check (`NO_INTIMACY_CHECK=false`)
- Ensures quality and appropriateness
- Worth the extra cost and latency

### For Development/Testing
- **Disable** intimacy check (`NO_INTIMACY_CHECK=true`)
- Faster iteration cycles
- Lower development costs
- Easier debugging (no retry complexity)

### For Load Testing
- **Disable** intimacy check (`NO_INTIMACY_CHECK=true`)
- Get accurate baseline performance metrics
- Avoid retry-related variability
- Test maximum throughput

## Related Configuration

Other feature flags in `.env`:

```bash
# Disable reply caching
NO_REPLY_CACHE=true

# Disable strategy planner
NO_STRATEGY_PLANNER=true

# Disable persona caching
NO_PERSONA_CACHE=true

# Disable intimacy check
NO_INTIMACY_CHECK=true
```

## Troubleshooting

### Issue: Configuration not taking effect

**Solution**: Restart the server after changing `.env`

```bash
# Stop server (Ctrl+C)
# Then restart
./start_server.sh  # Linux/macOS
.\start_server.ps1  # Windows
```

### Issue: Want to temporarily disable for testing

**Solution**: Use environment variable override

```bash
# Linux/macOS
NO_INTIMACY_CHECK=true python -m uvicorn app.main:app

# Windows PowerShell
$env:NO_INTIMACY_CHECK="true"; python -m uvicorn app.main:app
```

## See Also

- [Cache Fix Documentation](CACHE_FIX_DUPLICATE_ANALYSIS.md)
- [JSON Parsing Improvements](JSON_PARSING_IMPROVEMENTS.md)
- [Multimodal Provider Configuration](MULTIMODAL_PROVIDER_CONFIG.md)
