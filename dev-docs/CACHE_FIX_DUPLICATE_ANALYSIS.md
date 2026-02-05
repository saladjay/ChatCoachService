# Cache Fix: Duplicate Analysis Issue

## Problem

When both `scene_analysis` and `reply` generation were requested, the system was performing duplicate analysis:

1. `_scenario_analysis()` → `orchestrator.scenario_analysis()`
   - Context Build (1.51s)
   - Scene Analysis (1.11s)
   - **Total: 2.62s**

2. `_generate_reply()` → `orchestrator.generate_reply()`
   - **Context Build again (1.05s)** ❌
   - **Scene Analysis again (1.02s)** ❌
   - Persona Inference
   - Reply Generation
   - **Extra time: 2.07s**

**Total wasted time: ~2 seconds per request**

## Root Cause

### The Bug

In `app/services/orchestrator.py`, the `_get_cached_payload()` method had a logic error:

```python
# BEFORE (WRONG):
if self.cache_service is None or not request.resource or request.force_regenerate or request.resources:
    return None
```

**Problem:** The condition `or request.resources` meant:
- If `request.resources` exists (which it does in your case), skip cache
- This caused cache to NEVER be used when `resources` list was provided

### Why This Happened

The original logic was:
```
Skip cache if:
- No cache service OR
- No resource OR
- Force regenerate OR
- Resources list exists  ← WRONG!
```

Should have been:
```
Skip cache if:
- No cache service OR
- (No resource AND no resources list) OR
- Force regenerate
```

## Solution

### Fixed Logic

```python
# AFTER (CORRECT):
if self.cache_service is None or (not request.resource and not request.resources) or request.force_regenerate:
    return None
```

Now cache is skipped only when:
1. No cache service available
2. **Both** `resource` and `resources` are empty
3. Force regenerate flag is set

### Additional Improvements

1. **Better resource key selection:**
   ```python
   resource_key = request.resource or (request.resources[0] if request.resources else None)
   ```

2. **Added cache hit logging:**
   ```python
   logger.info(f"Cache hit for category={category}, resource={resource_key}")
   ```

3. **Early return for safety:**
   ```python
   if not resource_key:
       return None
   ```

## Impact

### Before Fix

```
Timeline:
0.00s - Start scenario_analysis
1.51s - Context Build complete
2.62s - Scene Analysis complete
2.62s - Start generate_reply
3.67s - Context Build complete (DUPLICATE!)
4.69s - Scene Analysis complete (DUPLICATE!)
5.xx s - Persona Inference
6.xx s - Reply Generation
```

**Total time: ~6+ seconds**

### After Fix

```
Timeline:
0.00s - Start scenario_analysis
1.51s - Context Build complete (cached)
2.62s - Scene Analysis complete (cached)
2.62s - Start generate_reply
2.62s - Context Build (cache hit!) ✅
2.62s - Scene Analysis (cache hit!) ✅
3.xx s - Persona Inference
4.xx s - Reply Generation
```

**Total time: ~4 seconds**
**Time saved: ~2 seconds (33% faster!)**

## Testing

### Verify Cache is Working

Look for these log messages:

**Cache hit (good):**
```
INFO - Cache hit for category=context_analysis, resource=https://...
INFO - Cache hit for category=scene_analysis, resource=https://...
```

**Cache miss (expected on first request):**
```
INFO - Context build took 1.51 seconds
INFO - Scene analysis took 1.11 seconds
```

**Cache hit on second request (expected):**
```
INFO - Context build took 0.01 seconds  ← Much faster!
INFO - Scene analysis took 0.01 seconds  ← Much faster!
```

### Test Scenarios

1. **First request (no cache):**
   - Should see full execution times
   - Should see cache write operations

2. **Second request (with cache):**
   - Should see "Cache hit" messages
   - Should see much faster execution times

3. **Different resource (no cache):**
   - Should see full execution times again
   - Each resource has its own cache

## Related Code

- `app/services/orchestrator.py` - `_get_cached_payload()` method
- `app/services/orchestrator.py` - `_append_cache_event()` method
- `app/services/orchestrator.py` - `scenario_analysis()` method
- `app/services/orchestrator.py` - `generate_reply()` method
- `app/api/v1/predict.py` - `_scenario_analysis()` function
- `app/api/v1/predict.py` - `_generate_reply()` function

## Cache Categories

The system caches these analysis results:

1. **context_analysis** - Context building results
2. **scene_analysis** - Scene analysis results
3. **persona_analysis** - Persona inference results
4. **strategy_plan** - Strategy planning results
5. **reply** - Generated replies

Each category is cached separately per:
- `session_id` (conversation)
- `resource` (image URL or content identifier)
- `scene` (scene type)

## Benefits

1. **Performance:** 33% faster when both scene_analysis and reply are requested
2. **Cost:** Reduced LLM API calls (saves money)
3. **Consistency:** Same analysis results used across the request
4. **Scalability:** Less load on LLM providers

## Future Improvements

### Option 1: Pre-warm Cache

When `prepare_generate_reply()` is called, it could pre-warm the cache for the next `generate_reply()` call.

### Option 2: Shared Cache Key

Use a shared cache key for the entire request to ensure all steps use the same cached data.

### Option 3: Cache Invalidation

Add cache TTL or invalidation logic to prevent stale data.

## Monitoring

Watch for these metrics:

- **Cache hit rate:** Should be >50% for repeated requests
- **Execution time:** Should be ~2s faster when cache hits
- **LLM API calls:** Should be reduced by ~2 calls per request

## Notes

- Cache is stored in Redis (if configured)
- Cache key includes: session_id, resource, scene, category
- Cache is per-resource, so different images have different cache
- Force regenerate flag bypasses cache
