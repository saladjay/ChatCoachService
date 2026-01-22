# Design Document: Phase 3 Output Optimization

## Overview

Phase 3 implements output optimization to reduce LLM output tokens by 40-60% through three main strategies:

1. **Reasoning Control**: Conditionally exclude reasoning fields from outputs
2. **Configuration Management**: Centralized settings for optimization features
3. **Length Constraints**: Token limits based on quality tiers

This design maintains backward compatibility while providing flexible optimization controls.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Configuration Layer                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ PromptConfig (app/core/config.py)                    │  │
│  │ - include_reasoning: bool                            │  │
│  │ - max_reply_tokens: int                              │  │
│  │ - use_compact_schemas: bool                          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Prompt Assembly Layer                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ PromptAssembler                                      │  │
│  │ - Applies reasoning control                          │  │
│  │ - Includes length constraints                        │  │
│  │ - Uses compact schemas                               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    LLM Adapter Layer                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ LLMCall                                              │  │
│  │ - max_tokens: int (enforced at API level)           │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
                        LLM API
```

## Components and Interfaces

### 1. PromptConfig Class

**Location**: `app/core/config.py`

```python
class PromptConfig(BaseModel):
    """Configuration for prompt optimization."""
    
    include_reasoning: bool = Field(
        default=False,
        description="Include reasoning fields in LLM outputs"
    )
    
    max_reply_tokens: int = Field(
        default=100,
        ge=20,
        le=500,
        description="Maximum tokens for reply generation"
    )
    
    use_compact_schemas: bool = Field(
        default=True,
        description="Use compact output schemas"
    )
    
    @classmethod
    def from_env(cls) -> "PromptConfig":
        """Load configuration from environment variables."""
        return cls(
            include_reasoning=os.getenv("PROMPT_INCLUDE_REASONING", "false").lower() == "true",
            max_reply_tokens=int(os.getenv("PROMPT_MAX_REPLY_TOKENS", "100")),
            use_compact_schemas=os.getenv("PROMPT_USE_COMPACT_SCHEMAS", "true").lower() == "true"
        )
```

### 2. REPLY_LENGTH_CONSTRAINTS

**Location**: `app/services/prompt_assembler.py`

```python
REPLY_LENGTH_CONSTRAINTS = {
    "cheap": {
        "max_tokens": 50,
        "guidance": "Keep replies very brief (1-2 sentences max)"
    },
    "normal": {
        "max_tokens": 100,
        "guidance": "Keep replies concise (2-3 sentences)"
    },
    "premium": {
        "max_tokens": 200,
        "guidance": "Provide detailed replies (3-5 sentences)"
    }
}
```

### 3. Enhanced LLMCall Schema

**Location**: `app/models/schemas.py` or `app/services/llm_adapter.py`

```python
@dataclass
class LLMCall:
    """LLM API call parameters."""
    task_type: str
    prompt: str
    quality: Literal["cheap", "normal", "premium"]
    user_id: str
    provider: str
    model: str
    max_tokens: Optional[int] = None  # NEW: Token limit
```

### 4. PromptAssembler Enhancements

**Location**: `app/services/prompt_assembler.py`

**New Methods**:

```python
def _build_output_schema_instruction(
    self, 
    include_reasoning: bool,
    max_tokens: int
) -> str:
    """Build output schema instruction based on optimization settings."""
    
def _apply_length_constraint(
    self,
    prompt: str,
    quality: str
) -> str:
    """Add length constraint guidance to prompt."""
```

## Data Models

### Compact Output Schemas (Already Implemented)

Phase 1 already implemented compact schemas. Phase 3 extends this with reasoning control:

**With Reasoning** (current):
```json
{
  "r": [
    ["Hello!", "emotional_resonance", "This creates warmth"],
    ["How are you?", "curiosity_hook", "Shows interest"]
  ],
  "adv": "Keep it friendly"
}
```

**Without Reasoning** (Phase 3):
```json
{
  "r": [
    ["Hello!", "emotional_resonance"],
    ["How are you?", "curiosity_hook"]
  ],
  "adv": "Keep it friendly"
}
```

**Token Savings**: ~40% when reasoning is excluded

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do.*

### Property 1: Reasoning Exclusion Consistency

*For any* LLM output, when `include_reasoning=False`, the output should not contain reasoning fields.

**Validates: Requirements 1.1, 1.4**

### Property 2: Configuration Loading Idempotence

*For any* environment configuration, loading configuration multiple times should produce the same result.

**Validates: Requirements 2.6**

### Property 3: Length Constraint Enforcement

*For any* quality tier, the `max_tokens` value should match the defined constraint for that tier.

**Validates: Requirements 3.5**

### Property 4: Token Reduction Achievement

*For any* set of test cases, disabling reasoning should reduce output tokens by at least 30%.

**Validates: Requirements 6.5**

### Property 5: Quality Preservation

*For any* generated reply, excluding reasoning should not change the reply text content.

**Validates: Requirements 5.1, 5.2**

### Property 6: Backward Compatibility

*For any* existing code, enabling all optimization features should not break functionality.

**Validates: Requirements 4.4**

### Property 7: Environment Variable Validation

*For any* invalid environment variable value, the system should use default values and not crash.

**Validates: Requirements 7.6**

## Error Handling

### Configuration Errors

1. **Invalid Environment Values**
   - Action: Log warning, use default value
   - Example: `PROMPT_MAX_REPLY_TOKENS=abc` → use default 100

2. **Out of Range Values**
   - Action: Clamp to valid range, log warning
   - Example: `PROMPT_MAX_REPLY_TOKENS=1000` → clamp to 500

### Runtime Errors

1. **LLM Output Exceeds max_tokens**
   - Action: Accept output, log for monitoring
   - Note: LLM APIs typically enforce limits

2. **Missing Configuration**
   - Action: Use defaults, continue operation
   - Log: Info level (not error)

## Testing Strategy

### Unit Tests

**File**: `tests/test_output_optimization.py`

1. **Test Reasoning Control**
   - Test output schema with reasoning enabled
   - Test output schema with reasoning disabled
   - Verify token count difference

2. **Test Configuration Loading**
   - Test loading from environment variables
   - Test default values
   - Test invalid value handling

3. **Test Length Constraints**
   - Test constraint lookup by quality tier
   - Test prompt modification with constraints
   - Test max_tokens assignment

### Integration Tests

**File**: `tests/integration/test_output_optimization.py`

1. **End-to-End Token Reduction**
   - Measure tokens with reasoning enabled
   - Measure tokens with reasoning disabled
   - Verify 40-60% reduction

2. **Quality Validation**
   - Generate replies with optimization
   - Compare quality metrics
   - Ensure no degradation

### Property-Based Tests

1. **Property 1**: Reasoning exclusion (100 iterations)
2. **Property 4**: Token reduction (100 iterations)
3. **Property 5**: Quality preservation (100 iterations)

## Implementation Plan

### Phase 3.1: Configuration (Day 1-2)

1. Add `PromptConfig` to `app/core/config.py`
2. Update `AppConfig` to include `prompt: PromptConfig`
3. Add environment variable loading
4. Update `.env.example`

### Phase 3.2: Reasoning Control (Day 2-3)

1. Update `PromptAssembler` to accept `include_reasoning` parameter
2. Modify output schema instructions based on setting
3. Update compact schema parsing to handle both formats
4. Test reasoning exclusion

### Phase 3.3: Length Constraints (Day 3-4)

1. Add `REPLY_LENGTH_CONSTRAINTS` to `PromptAssembler`
2. Add `max_tokens` field to `LLMCall`
3. Update LLM Adapter to pass `max_tokens` to API
4. Add length guidance to prompts
5. Test length constraint enforcement

### Phase 3.4: Integration (Day 4-5)

1. Update services to use `PromptConfig`
2. Wire configuration through dependency injection
3. Run integration tests
4. Measure token reduction
5. Validate quality preservation

### Phase 3.5: Documentation (Day 5)

1. Document configuration options
2. Create usage examples
3. Update deployment guide
4. Write completion report

## Performance Considerations

### Token Reduction Breakdown

| Optimization | Token Reduction | Cumulative |
|--------------|-----------------|------------|
| Exclude reasoning | 40% | 40% |
| Length constraints | 20% | 52% |
| **Total** | **~50%** | **~50%** |

### Latency Impact

- Configuration loading: +5ms (startup only)
- Prompt assembly: +2ms per request
- Total impact: Negligible (<5ms per request)

## Deployment Strategy

### Gradual Rollout

1. **Phase 1**: Deploy with reasoning enabled (no change)
2. **Phase 2**: Enable for 10% of traffic
3. **Phase 3**: Monitor metrics for 48 hours
4. **Phase 4**: Increase to 50% if metrics are good
5. **Phase 5**: Full rollout

### Rollback Plan

```python
# Quick rollback via environment variables
PROMPT_INCLUDE_REASONING=true
PROMPT_MAX_REPLY_TOKENS=200
PROMPT_USE_COMPACT_SCHEMAS=false
```

### Monitoring Metrics

1. **Token Usage**
   - Average output tokens per request
   - Token reduction percentage
   - Cost savings

2. **Quality Metrics**
   - Reply relevance scores
   - Intimacy check pass rate
   - User satisfaction

3. **Performance Metrics**
   - Latency (p50, p95, p99)
   - Error rate
   - API success rate

## Security Considerations

1. **Environment Variable Validation**
   - Validate all inputs
   - Prevent injection attacks
   - Use safe defaults

2. **Configuration Access**
   - Read-only after initialization
   - No runtime modification
   - Audit configuration changes

## Future Enhancements

1. **Dynamic Optimization**
   - Adjust settings based on load
   - Per-user optimization levels
   - A/B testing framework

2. **Advanced Length Control**
   - Sentence boundary detection
   - Smart truncation
   - Priority-based content selection

3. **Quality-Aware Optimization**
   - Adjust optimization based on quality metrics
   - Automatic rollback on quality degradation
   - Machine learning-based optimization

## Success Metrics

### Must-Have (P0)
- ✅ 40%+ output token reduction
- ✅ No quality degradation
- ✅ All tests passing
- ✅ Configuration working

### Should-Have (P1)
- ✅ 50%+ output token reduction
- ✅ <5ms latency impact
- ✅ Complete documentation
- ✅ Monitoring dashboard

### Nice-to-Have (P2)
- ⭐ 60%+ output token reduction
- ⭐ Dynamic optimization
- ⭐ A/B testing framework
- ⭐ ML-based optimization

## References

- Phase 1: Schema Compression (completed)
- Phase 2: Prompt Layering (completed)
- LLM API Documentation
- Pydantic Configuration Management
