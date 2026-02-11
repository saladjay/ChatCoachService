# Generation vs Merge Step 调用次数分析

## 观察到的数据

```
LATENCY SUMMARY BY TASK_TYPE
--------------------------------------------------------------------------------
Type                              N   Mean(ms)        P50        P90        Min        Max
--------------------------------------------------------------------------------
merge_step                       99       9349       7971      12459       5677      12860
generation                      170       3506       1956       7468       1548       8325
```

**关键发现**：
- `generation` 调用次数 (170) 约为 `merge_step` (99) 的 **1.72 倍**
- 这个比例接近但不完全是 2:1

## 原因分析

### 1. 每个请求的调用流程

#### 单个图片/对话的处理流程

```
1 个请求 → 1 次 merge_step → 1-2 次 generation
```

**详细流程**：

1. **merge_step (1 次)**：
   - 解析截图，提取对话和场景信息
   - 每个图片/资源调用 1 次

2. **generation (可能多次)**：
   - **prepare_generate_reply**：预处理阶段（如果有多个资源）
   - **generate_reply**：实际生成回复
   - **重试机制**：如果亲密度检查失败，可能重试

### 2. 为什么 generation 更多？

#### 原因 A：多资源处理

在 `_generate_reply` 函数中：

```python
for resource_index, (resources, dialog, list_image_result) in enumerate(analysis_queue):
    if resource_index < len(analysis_queue) - 1:
        await orchestrator.prepare_generate_reply(orchestrator_request)  # 预处理
        continue
    
    orchestrator_response = await orchestrator.generate_reply(orchestrator_request)  # 实际生成
```

**场景**：
- 如果一个请求有 2 个图片/资源
- 第 1 个：调用 `prepare_generate_reply`（可能包含 LLM 调用）
- 第 2 个：调用 `generate_reply`（包含 LLM 调用）

#### 原因 B：重试机制（已禁用亲密度检查）

在 `orchestrator.py` 中：

```python
for attempt in range(self.config.max_retries):
    # Generate reply
    reply_result = await self._execute_step(
        exec_ctx,
        f"reply_generation_attempt_{attempt + 1}",
        self.reply_generator.generate_reply,
        reply_input,
    )
    
    # Check intimacy (如果启用)
    if not settings.no_intimacy_check:
        intimacy_result = await self._execute_step(...)
        if intimacy_result.passed:
            return reply_result, intimacy_result
        # 如果失败，继续下一次重试
```

**注意**：你提到已经禁用了亲密度检查，所以这个因素应该不会导致重试。

#### 原因 C：step_end 事件的统计

在 `analyze_trace.py` 中，我们从 `step_end` 事件推断 task_type：

```python
if "reply_generation" in step_name or "generation" in step_name:
    task_type = "generation"
```

**可能的 step_end 事件**：
- `reply_generation_attempt_1`
- `reply_generation_attempt_2`（如果重试）
- 其他包含 "generation" 的步骤

### 3. 实际比例计算

假设 99 个请求：
- 每个请求：1 次 merge_step
- 总共：99 次 merge_step ✓

如果：
- 70% 的请求只有 1 个资源：70 × 1 = 70 次 generation
- 30% 的请求有 2 个资源：30 × 2 = 60 次 generation
- 部分请求有重试：~40 次额外 generation

总计：70 + 60 + 40 = 170 次 generation ✓

## 验证方法

### 方法 1：检查 trace 日志

查看实际的 trace 日志，统计：

```bash
# 统计每个 session 的 generation 调用次数
grep "reply_generation_attempt" trace.jsonl | \
  jq -r '.conversation_id' | \
  sort | uniq -c | sort -rn | head -20
```

### 方法 2：添加详细日志

在 `_generate_reply` 中添加日志：

```python
logger.info(f"Processing {len(analysis_queue)} resources for session {request.session_id}")
for resource_index, (resources, dialog, list_image_result) in enumerate(analysis_queue):
    logger.info(f"Resource {resource_index + 1}/{len(analysis_queue)}")
```

### 方法 3：分析 step_end 事件

检查 trace 中的 step_end 事件：

```bash
# 统计不同类型的 generation 步骤
grep "step_end" trace.jsonl | \
  jq -r 'select(.step_name | contains("generation")) | .step_name' | \
  sort | uniq -c
```

## 预期行为

### 正常情况（无重试，单资源）

```
1 请求 → 1 merge_step + 1 generation
比例：1:1
```

### 多资源情况

```
1 请求（2 个图片）→ 2 merge_step + 2 generation
比例：1:1
```

但如果 merge_step 是批量处理的：
```
1 请求（2 个图片）→ 1 merge_step + 2 generation
比例：1:2
```

### 有重试的情况

```
1 请求 → 1 merge_step + 2 generation（1 次失败 + 1 次成功）
比例：1:2
```

## 结论

**1.72:1 的比例可能来自**：

1. **多资源处理** (最可能)
   - 部分请求包含多个图片/资源
   - 每个资源可能触发独立的 generation 调用
   - 但 merge_step 可能是批量处理的

2. **prepare_generate_reply 调用**
   - 在多资源场景中，前面的资源调用 prepare
   - 最后一个资源调用实际的 generate
   - 如果 prepare 也包含 LLM 调用，会被统计为 generation

3. **step_end 事件的统计方式**
   - 可能有其他包含 "generation" 的步骤被统计进来
   - 需要检查 trace 日志确认

## 建议

### 1. 添加更详细的统计

修改 `analyze_trace.py`，区分不同类型的 generation：

```python
if "reply_generation_attempt" in step_name:
    task_type = "reply_generation"
elif "prepare_generate" in step_name:
    task_type = "prepare_generation"
elif "generation" in step_name:
    task_type = "generation"
```

### 2. 检查实际的 trace 数据

```bash
# 查看所有 generation 相关的 step_name
grep "step_end" trace.jsonl | \
  jq -r 'select(.step_name | contains("generation")) | .step_name' | \
  sort | uniq -c | sort -rn
```

### 3. 优化多资源处理

如果确认是多资源导致的，考虑：
- 批量处理多个资源的 generation
- 减少不必要的 prepare 调用
- 优化资源处理流程

## 更新日期

2026-02-05
