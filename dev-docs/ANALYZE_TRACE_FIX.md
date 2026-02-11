# Analyze Trace Fix - None Value Handling & Step End Improvements

## 问题

### 问题 1：None 值导致格式化错误

`scripts/analyze_trace.py` 在处理 trace 文件时，如果 LLM 调用的 `model`、`provider` 或 `task_type` 字段为 `None`，会导致格式化错误：

```
TypeError: unsupported format string passed to NoneType.__format__
```

### 问题 2：step_end 事件处理不当

原有逻辑将所有 `step_end` 事件都当作 LLM 调用，导致：
- 非 LLM 步骤（如 `persona_inference`）被错误统计
- 统计数据不准确
- 无法区分真正的 LLM 调用和普通步骤完成

### 问题 3：task_type 推断不足

`step_end` 事件的 `result` 中包含 provider/model，但顶层没有 task_type，导致大量 `unknown` task_type。

### 错误位置

```python
print(f"{i:<4} {call['task_type']:<20} {call['model']:<20} "
      f"{call['input_tokens']:<8} {call['output_tokens']:<8} "
      f"{call['total_tokens']:<8} ${call['cost_usd']:<11.6f}")
```

当 `call['model']` 或 `call['task_type']` 为 `None` 时，Python 的字符串格式化无法处理。

## 根本原因

在 `extract_llm_calls()` 函数中，从 trace 事件提取字段时使用了 `entry.get()`，如果字段不存在或为 `None`，会直接传递 `None` 值：

```python
llm_calls.append({
    "task_type": entry.get("task_type"),      # 可能是 None
    "provider": entry.get("provider"),        # 可能是 None
    "model": entry.get("model"),              # 可能是 None
    ...
})
```

## 解决方案

### 方案 1：为 None 值提供默认值

在提取字段时，为可能为 `None` 的字段提供默认值 `"unknown"`：

#### 修改：llm_call_end 事件处理

```python
llm_calls.append({
    "timestamp": entry.get("ts"),
    "task_type": entry.get("task_type") or "unknown",      # 默认值
    "provider": entry.get("provider") or "unknown",        # 默认值
    "model": entry.get("model") or "unknown",              # 默认值
    ...
})
```

### 方案 2：智能过滤 step_end 事件

只有当 `step_end` 包含 LLM 相关元数据时才视为 LLM 调用：

```python
# Check if this step_end contains LLM call information
has_llm_metadata = (
    entry.get("provider") or 
    entry.get("model") or 
    entry.get("input_tokens") or 
    entry.get("output_tokens") or 
    entry.get("cost_usd")
)

# Also check if result contains LLM metadata
result = entry.get("result", {})
if isinstance(result, dict):
    has_llm_metadata = has_llm_metadata or (
        result.get("provider") or 
        result.get("model") or 
        result.get("input_tokens") or 
        result.get("output_tokens") or 
        result.get("cost_usd")
    )

# Only add if this is actually an LLM call
if has_llm_metadata:
    # Extract metadata from top level or result
    provider = entry.get("provider") or result.get("provider") or "unknown"
    model = entry.get("model") or result.get("model") or "unknown"
    ...
```

### 方案 3：从 step_name 推断 task_type

当 `step_end` 没有 task_type 时，从 step_name 推断：

```python
# Infer task_type from step_name if not provided
task_type = entry.get("task_type")
if not task_type:
    step_name = entry.get("step_name", "")
    if "merge_step" in step_name:
        task_type = "merge_step"
    elif "reply_generation" in step_name or "generation" in step_name:
        task_type = "generation"
    elif "scene" in step_name:
        task_type = "scene"
    elif "persona" in step_name:
        task_type = "persona"
    elif "context" in step_name:
        task_type = "context"
    else:
        task_type = "unknown"
```

## 测试

创建了 `tests/test_analyze_trace_unit.py` 单元测试来验证修复：

### 测试场景

1. **None 值处理**：验证所有 None 值都被替换为 "unknown"
2. **print_summary 函数**：验证格式化输出不会抛出 TypeError
3. **step_end 事件过滤**：验证只统计包含 LLM 元数据的 step_end
4. **task_type 推断**：验证从 step_name 正确推断 task_type

### 运行测试

```bash
python tests/test_analyze_trace_unit.py
```

### 测试结果

```
================================================================================
RUNNING UNIT TESTS FOR analyze_trace.py
================================================================================

TEST: None Value Handling
✓ Successfully parsed 3 LLM calls
✓ Correct number of LLM calls (non-LLM step_end filtered out)
✓ All None values handled correctly

TEST: print_summary Function
✓ print_summary executed successfully without TypeError

TEST: step_end Event Filtering
✓ Extracted 2 LLM calls from 3 step_end events
✓ Correctly filtered out non-LLM step_end
✓ First call has correct metadata from top level
✓ Second call has correct metadata from result field

TEST: task_type Inference from step_name
✓ Correctly inferred 'merge_step' from 'merge_step_llm'
✓ Correctly inferred 'generation' from 'reply_generation_attempt_1'

✓ ALL TESTS PASSED!
```

### 真实 Trace 数据测试

使用真实的线上 trace 数据（`test_real_trace.jsonl`）测试改进效果：

**改进前的问题**：
- 将所有 `step_end` 都当作 LLM 调用
- 包含非 LLM 步骤（如 `persona_inference`）
- 大量 `unknown` task_type

**改进后的结果**：
```
OVERALL STATISTICS
--------------------------------------------------------------------------------
  Total LLM Calls:    42
  Total Input Tokens: 42,694
  Total Output Tokens: 15,208
  Total Tokens:       57,902
  Total Cost:         $0.005096
  Average Latency:    5017ms

LATENCY SUMMARY BY TASK_TYPE
--------------------------------------------------------------------------------
Type                              N   Mean(ms)        P50        P90        Min        Max
--------------------------------------------------------------------------------
merge_step                       10       8759       7218      12431       5697      12451
generation                       32       3848       1896       7362       1651       7411
```

**改进效果**：
- ✅ 正确识别 42 个真正的 LLM 调用
- ✅ 只有 2 种 task_type：`merge_step` 和 `generation`（无 `unknown`）
- ✅ 正确过滤掉非 LLM 步骤（如 `persona_inference`）
- ✅ 从 `step_name` 正确推断 task_type
- ✅ 从 `result` 字段提取 provider/model 信息

## 影响范围

### 修改的文件

- `scripts/analyze_trace.py`：在 `extract_llm_calls()` 函数中添加默认值

### 受益的功能

所有使用这些字段的函数都受益：
- `print_summary()`：打印摘要信息
- `print_detailed_call()`：打印详细调用信息
- `compare_traces()`：比较两个 trace 文件

## 向后兼容性

- ✅ 完全向后兼容
- ✅ 不影响现有的正常数据
- ✅ 只为 `None` 值提供默认值
- ✅ 不改变任何函数签名或输出格式

## 为什么会出现 None 值？

可能的原因：
1. **日志记录不完整**：某些 LLM 调用没有记录完整的元数据
2. **错误处理**：LLM 调用失败时，某些字段可能未设置
3. **新功能**：新增的 LLM 调用类型可能还没有完整的日志记录
4. **merge_step 集成**：merge_step 的日志记录可能与传统调用不同

## 未来改进

1. **日志标准化**：确保所有 LLM 调用都记录完整的元数据
2. **验证机制**：在日志记录时验证必需字段
3. **更好的默认值**：根据上下文提供更有意义的默认值
4. **告警机制**：当检测到 None 值时发出警告

## 相关文件

- `scripts/analyze_trace.py`：主要修改文件
- `tests/test_analyze_trace_unit.py`：单元测试
- `scripts/analyze_real_trace_patterns.py`：真实数据模式分析工具
- `app/services/orchestrator.py`：LLM 调用的日志记录

## 更新日期

2026-02-05
