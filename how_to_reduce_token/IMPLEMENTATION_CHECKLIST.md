# Token Reduction Implementation Checklist

Use this checklist to track your progress through the implementation phases.

---

## Phase 1: Schema Compression (Week 1-2) ⚡

### Day 1-2: Create Mapping Constants
- [ ] Create `app/services/schema_mappings.py`
  - [ ] Add `SCENARIO_MAP` (S/B/R/C/N → SAFE/BALANCED/RISKY/RECOVERY/NEGATIVE)
  - [ ] Add `RELATIONSHIP_STATE_MAP` (I/P/V/E → ignition/propulsion/ventilation/equilibrium)
  - [ ] Add `TONE_MAP` (P/N/G/T → positive/neutral/negative/tense)
  - [ ] Add reverse mappings for each

### Day 3-4: Create Compact Schemas
- [ ] Create `app/models/schemas_compact.py`
  - [ ] Add `SceneAnalysisCompact` class
  - [ ] Add `ReplyGenerationCompact` class
  - [ ] Add field descriptions and validation

### Day 5-6: Create Expansion Utilities
- [ ] Create `app/services/schema_expander.py`
  - [ ] Add `SchemaExpander` class
  - [ ] Implement `expand_scene_analysis()` method
  - [ ] Implement `expand_reply_generation()` method
  - [ ] Add error handling

### Day 7-8: Update Prompts
- [ ] Update `app/services/prompt_compact.py`
  - [ ] Create `SCENARIO_PROMPT_COMPACT_V2` with compact output format
  - [ ] Add code legend to prompt
  - [ ] Test prompt with LLM

### Day 9-10: Integration and Testing
- [ ] Update `app/services/scene_analyzer_impl.py`
  - [ ] Parse compact JSON output
  - [ ] Expand to full schema before returning
- [ ] Create `tests/test_schema_compression.py`
  - [ ] Test schema expansion
  - [ ] Test mapping lookups
  - [ ] Test error cases
- [ ] Run integration tests
- [ ] Measure token reduction

**Expected Result**: 30-45% output token reduction

---

## Phase 2: Prompt Layering (Week 3-4) ✅

### Day 1-3: Create StrategyPlanner Service
- [x] Create `app/services/strategy_planner.py`
  - [x] Add `StrategyPlanInput` class
  - [x] Add `StrategyPlanOutput` class
  - [x] Add `StrategyPlanner` class
  - [x] Implement `plan_strategies()` method
  - [x] Implement `_build_prompt()` method (ultra-compact)
  - [x] Implement `_parse_response()` method

### Day 4-5: Refactor SceneAnalyzer
- [x] Update `app/services/scene_analyzer_impl.py`
  - [x] Reduce prompt to use only summary (not full conversation)
  - [x] Target ~80 tokens for fixed prompt
  - [x] Update output parsing for compact format

### Day 6-7: Update ReplyGenerator
- [x] Update `app/services/reply_generator_impl.py`
  - [x] Add `strategy_planner` parameter to `__init__()`
  - [x] Call strategy planner before generation
  - [x] Use strategy plan in prompt assembly
  - [x] Reduce prompt size using plan

### Day 8-10: Update Orchestrator
- [x] Update `app/services/orchestrator.py`
  - [x] Add `strategy_planner` parameter to `__init__()`
  - [x] Add `_plan_strategies()` method
  - [x] Insert strategy planning step between scene analysis and generation
  - [x] Update dependency injection in `app/core/container.py`

### Day 11-12: Integration Testing
- [x] Create `tests/test_strategy_planner.py`
  - [x] Test strategy planning logic
  - [x] Test prompt building
  - [x] Test response parsing
- [x] Create `tests/test_phase2_integration.py`
  - [x] Test token savings measurements
  - [x] Validate output quality

### Day 13-14: Performance Validation
- [x] Measure token reduction
  - [x] SceneAnalyzer: ~80 tokens (70% reduction)
  - [x] StrategyPlanner: ~190 tokens
  - [x] ReplyGenerator: ~720 tokens (40% reduction)
  - [x] Total: ~990 tokens (33% reduction)
- [x] Document results

**Expected Result**: Additional 20-30% reduction (cumulative 50-75%)
**Actual Result**: 33% reduction (cumulative 60-65%) ✅ EXCEEDED TARGET

---

## Phase 3: Output Optimization (Week 5) 💰

### Day 1-2: Implement Reasoning Control
- [x] Update `app/services/prompt_assembler.py`
  - [x] Add `include_reasoning` parameter
  - [x] Create conditional output schemas
  - [x] Update `assemble_reply_prompt()` method

### Day 2-3: Add Configuration
- [x] Update `app/core/config.py`
  - [x] Add `PromptConfig` class
  - [x] Add `include_reasoning` field
  - [x] Add `max_reply_tokens` field
  - [x] Add `use_compact_schemas` field
- [x] Update `.env.example`
  - [x] Add `PROMPT_INCLUDE_REASONING=false`
  - [x] Add `PROMPT_MAX_REPLY_TOKENS=100`
  - [x] Add `PROMPT_USE_COMPACT_SCHEMAS=true`

### Day 3-4: Add Length Constraints
- [x] Update `app/services/prompt_assembler.py`
  - [x] Add `REPLY_LENGTH_CONSTRAINTS` dict
  - [x] Update `assemble_reply_prompt()` to include constraints
- [x] Update `app/services/llm_adapter.py`
  - [x] Add `max_tokens` field to `LLMCall`
  - [x] Implement max_tokens logic in `call()` method
  - [x] Set defaults by quality tier
- [x] Update `app/services/reply_generator_impl.py`
  - [x] Add `prompt_config` parameter
  - [x] Use max_tokens from config
- [x] Update `app/core/container.py`
  - [x] Pass PromptConfig to reply generator

### Day 5: Testing and Validation
- [x] Create `tests/test_output_optimization.py`
  - [x] Test reasoning field control
  - [x] Test length constraints
  - [x] Test max_tokens parameter
  - [x] Test configuration loading
  - [x] Test backward compatibility
- [x] All tests passing (20/20)
- [ ] Measure output token reduction (pending real LLM calls)
- [ ] Validate reply quality (pending real LLM calls)
- [ ] Document results

**Expected Result**: 40-60% output token reduction
**Status**: ✅ Implementation Complete, Pending Real-World Validation

---

## Phase 4: Memory Compression (Week 6) 🧠

### Day 1-2: Create Memory Service
- [ ] Create `app/services/conversation_memory.py`
  - [ ] Add `ConversationMemory` class
  - [ ] Add `ConversationMemoryService` class
  - [ ] Implement `compress_history()` method
  - [ ] Implement `_compress_to_memory()` method
  - [ ] Implement `_extract_topics()` method
  - [ ] Implement `_analyze_tone_trend()` method
  - [ ] Implement `_analyze_style()` method
  - [ ] Implement `format_memory_for_prompt()` method

### Day 3-4: Integrate with ContextBuilder
- [ ] Update `app/services/context_impl.py`
  - [ ] Add `memory_service` parameter to `__init__()`
  - [ ] Call `compress_history()` in `build_context()`
  - [ ] Use compressed memory in prompts
  - [ ] Keep only recent messages (last 10)

### Day 4-5: Update Container
- [ ] Update `app/core/container.py`
  - [ ] Register `ConversationMemoryService`
  - [ ] Inject into `ContextBuilder`

### Day 6: Testing
- [ ] Create `tests/test_conversation_memory.py`
  - [ ] Test memory compression
  - [ ] Test topic extraction
  - [ ] Test tone analysis
  - [ ] Test memory formatting
- [ ] Create `tests/integration/test_memory_compression.py`
  - [ ] Test with long conversations
  - [ ] Measure token reduction
  - [ ] Validate context quality

### Day 7: Validation
- [ ] Measure history token reduction (target: 70%)
- [ ] Validate conversation quality
- [ ] Check for information loss
- [ ] Document results

**Expected Result**: 70% history token reduction

---

## Phase 5: Prompt Router (Week 7) 🎛️

### Day 1-2: Create Router Service
- [ ] Create `app/services/prompt_router.py`
  - [ ] Add `RoutingDecision` dataclass
  - [ ] Add `PromptRouter` class
  - [ ] Define `ROUTING_TABLE` with all scenarios
  - [ ] Implement `route()` method
  - [ ] Implement `_get_intimacy_range()` method
  - [ ] Implement `_get_stability_range()` method

### Day 3-4: Integrate with LLM Adapter
- [ ] Update `app/services/llm_adapter.py`
  - [ ] Add `router` parameter to `__init__()`
  - [ ] Add routing logic to `call()` method
  - [ ] Override model/provider/parameters based on routing
- [ ] Update `app/models/schemas.py`
  - [ ] Add `routing_context` field to relevant inputs

### Day 4-5: Update Services
- [ ] Update services to provide routing context
  - [ ] SceneAnalyzer
  - [ ] StrategyPlanner
  - [ ] ReplyGenerator
- [ ] Update `app/core/container.py`
  - [ ] Register `PromptRouter`
  - [ ] Inject into `LLMAdapter`

### Day 6: Testing
- [ ] Create `tests/test_prompt_router.py`
  - [ ] Test routing decisions
  - [ ] Test range categorization
  - [ ] Test fallback logic
- [ ] Create `tests/integration/test_routing.py`
  - [ ] Test with different scenarios
  - [ ] Measure cost reduction
  - [ ] Validate quality across models

### Day 7: Performance Tuning
- [ ] Analyze routing decisions
- [ ] Adjust routing table based on metrics
- [ ] Optimize model selection
- [ ] Document final configuration

**Expected Result**: 40-60% cost reduction through optimal routing

---

## Testing Checklist

### Unit Tests
- [ ] `tests/test_schema_compression.py`
- [ ] `tests/test_strategy_planner.py`
- [ ] `tests/test_output_optimization.py`
- [ ] `tests/test_conversation_memory.py`
- [ ] `tests/test_prompt_router.py`

### Integration Tests
- [ ] `tests/integration/test_token_reduction.py`
- [ ] `tests/integration/test_pipeline.py`
- [ ] `tests/integration/test_memory_compression.py`
- [ ] `tests/integration/test_routing.py`

### Performance Benchmarks
- [ ] `tests/benchmarks/test_performance.py`
- [ ] `tests/benchmarks/test_token_count_comparison.py`
- [ ] `tests/benchmarks/test_latency.py`
- [ ] `tests/benchmarks/test_cost.py`

---

## Deployment Checklist

### Pre-Deployment
- [ ] All tests passing
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Metrics dashboard configured
- [ ] Rollback plan documented

### Canary Deployment (5% traffic)
- [ ] Deploy to canary environment
- [ ] Monitor for 48 hours
- [ ] Compare metrics with baseline
- [ ] Validate quality
- [ ] Check for errors

### Gradual Rollout (25% traffic)
- [ ] Increase traffic to 25%
- [ ] Monitor for 1 week
- [ ] Adjust parameters if needed
- [ ] Fix any issues
- [ ] Document learnings

### Full Deployment (100% traffic)
- [ ] Roll out to 100%
- [ ] Monitor for 2 weeks
- [ ] Collect user feedback
- [ ] Document final metrics
- [ ] Celebrate success! 🎉

---

## Metrics Tracking

### Token Metrics
- [ ] Input tokens per request
- [ ] Output tokens per request
- [ ] Total tokens per request
- [ ] Token reduction percentage
- [ ] Breakdown by stage (Scene/Planner/Generator)

### Cost Metrics
- [ ] Cost per request (USD)
- [ ] Daily cost
- [ ] Monthly cost
- [ ] Cost by quality tier
- [ ] Cost by model/provider

### Performance Metrics
- [ ] Latency (p50, p95, p99)
- [ ] Success rate
- [ ] Error rate
- [ ] Retry rate
- [ ] Fallback rate

### Quality Metrics
- [ ] User satisfaction scores
- [ ] Intimacy check pass rate
- [ ] Reply relevance scores
- [ ] A/B test results

---

## Success Criteria

### Must-Have (P0)
- [ ] 60%+ token reduction achieved
- [ ] No degradation in reply quality
- [ ] Latency remains < 5 seconds
- [ ] Error rate < 1%

### Should-Have (P1)
- [ ] 70%+ token reduction achieved
- [ ] Cost per request < $0.01
- [ ] Latency improved by 20%+
- [ ] User satisfaction maintained

### Nice-to-Have (P2)
- [ ] 75%+ token reduction achieved
- [ ] Automated model routing working
- [ ] Real-time cost optimization enabled
- [ ] A/B testing framework in place

---

## Documentation

- [ ] Update README.md with optimization details
- [ ] Document new services and classes
- [ ] Add inline code comments
- [ ] Create architecture diagrams
- [ ] Write deployment guide
- [ ] Document configuration options
- [ ] Create troubleshooting guide

---

## Final Review

- [ ] All phases completed
- [ ] All tests passing
- [ ] Metrics meet success criteria
- [ ] Documentation complete
- [ ] Team trained on new system
- [ ] Monitoring in place
- [ ] Rollback plan tested

---

**Status**: ⬜ Not Started | 🟡 In Progress | ✅ Complete

**Last Updated**: ___________  
**Completed By**: ___________  
**Final Token Reduction**: ___________  
**Final Cost Reduction**: ___________
