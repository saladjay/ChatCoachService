# 缓存行为分析：Premium 失败时的缓存内容

## 场景描述

当 multimodal 模型成功完成并返回给用户后，premium 任务在后台失败或返回错误。

### 时间线

```
t=0.0s: 启动 multimodal 和 premium 任务
t=0.5s: multimodal 完成（✅ 成功）
t=0.5s: 缓存 multimodal 结果
t=0.5s: 返回响应给用户 ← REQUEST 返回
t=0.5s: 创建后台任务等待 premium
t=2.0s: premium 完成（❌ 失败/错误）
t=2.0s: 后台任务尝试缓存 premium 结果
```

## 缓存内容分析

### 情况 1：Multimodal 成功，Premium 失败

#### 缓存中的内容

**✅ 缓存包含 multimodal 的结果**

```json
{
  "context_analysis": {
    "conversation": [...],
    "conversation_summary": "...",
    "emotion_state": "neutral",
    "current_intimacy_level": 50,
    "risk_flags": [],
    "_model": "mistralai/ministral-3b-2512",
    "_strategy": "multimodal"
  },
  "scene_analysis": {
    "scenario": "SAFE",
    "intimacy_level": 50,
    "relationship_state": "维持",
    "recommended_scenario": "SAFE",
    "recommended_strategies": ["soft_callback", "neutral_open_question", "empathetic_ack"],
    "_model": "mistralai/ministral-3b-2512",
    "_strategy": "multimodal"
  }
}
```

#### Premium 失败的处理

Premium 后台任务会捕获异常并记录日志，但**不会覆盖已有的缓存**：

```python
except Exception as e:
    logger.warning(f"[{conversation_id}] Background: Failed to cache premium result: {e}")
    import traceback
    logger.debug(f"[{conversation_id}] Background: Traceback: {traceback.format_exc()}")
```

**关键点**：
- ❌ Premium 结果**不会**被缓存
- ✅ Multimodal 结果**保持不变**
- ✅ 下次请求会使用 multimodal 的缓存结果

### 情况 2：Premium 返回无效 JSON

如果 premium 返回了结果，但 JSON 无效或验证失败：

```python
if premium_result:
    premium_parsed = parse_json_with_markdown(premium_result.text)
    if validate_merge_step_result(premium_parsed):
        # 缓存 premium 结果
    else:
        logger.warning(f"[{conversation_id}] Background: Premium result invalid, not caching")
```

**结果**：
- ❌ Premium 结果**不会**被缓存（验证失败）
- ✅ Multimodal 结果**保持不变**
- ⚠️ 日志会显示：`Premium result invalid, not caching`

### 情况 3：Premium 超时

如果 premium 任务超过 30 秒（默认）：

```python
except asyncio.TimeoutError:
    logger.warning(f"[{conversation_id}] Background: Premium task timeout after {timeout}s")
```

**结果**：
- ❌ Premium 结果**不会**被缓存（超时）
- ✅ Multimodal 结果**保持不变**
- ⚠️ 日志会显示：`Premium task timeout after 30s`

### 情况 4：Premium 返回 None

如果 premium 任务返回 None：

```python
if premium_result:
    # 缓存逻辑
else:
    logger.warning(f"[{conversation_id}] Background: Premium result is None")
```

**结果**：
- ❌ Premium 结果**不会**被缓存
- ✅ Multimodal 结果**保持不变**
- ⚠️ 日志会显示：`Premium result is None`

## 缓存覆盖行为

### 重要：缓存是否会被覆盖？

让我们看看缓存服务的 `append_event` 方法：

```python
await cache_service.append_event(
    session_id=conversation_id,
    category="context_analysis",
    resource=resource,
    payload=premium_context_data,
    scene=scene
)
```

根据 `SessionCategorizedCacheService` 的实现：

1. **`append_event` 会追加新事件**
2. **`get_resource_category_last` 会返回最新的事件**

这意味着：
- ✅ 如果 premium 成功缓存，它会**覆盖** multimodal 的结果（因为是最新的）
- ❌ 如果 premium 失败，multimodal 的结果**保持为最新**

### 缓存时间线

```
t=0.5s: append_event(context_analysis, multimodal_data)  # 第一个事件
t=2.0s: append_event(context_analysis, premium_data)     # 第二个事件（如果成功）

get_resource_category_last() 返回：
- 如果 premium 成功：返回 premium_data（最新）
- 如果 premium 失败：返回 multimodal_data（唯一）
```

## 日志示例

### Premium 失败的日志

```
[1770695546596] Premium task still running, will cache in background
[1770695546596] Background: Premium task completed, processing result
[1770695546596] Background: Failed to cache premium result: 'MergeStepAdapter' object has no attribute 'to_results'
```

### Premium 验证失败的日志

```
[1770695546596] Premium task still running, will cache in background
[1770695546596] Background: Premium task completed, processing result
[1770695546596] Background: Premium result invalid, not caching
```

### Premium 超时的日志

```
[1770695546596] Premium task still running, will cache in background
[1770695546596] Background: Premium task timeout after 30s
```

## 总结

### 缓存内容

当 multimodal 成功但 premium 失败时：

| 缓存字段 | 内容 | 来源 |
|---------|------|------|
| `context_analysis` | ✅ Multimodal 的结果 | multimodal |
| `scene_analysis` | ✅ Multimodal 的结果 | multimodal |
| `_model` | `mistralai/ministral-3b-2512` | multimodal |
| `_strategy` | `multimodal` | multimodal |

### 行为特点

1. **安全性** ✅
   - Premium 失败不会影响已有的缓存
   - 用户始终能获得有效的结果

2. **一致性** ✅
   - 缓存中的 `_model` 和 `_strategy` 准确反映了数据来源
   - 下次请求会知道使用的是 multimodal 的结果

3. **可观测性** ✅
   - 日志清楚地记录了 premium 失败的原因
   - 可以通过日志追踪问题

4. **性能** ✅
   - Premium 失败不会阻塞主请求
   - 不会浪费已有的 multimodal 结果

### 下次请求的行为

当下次请求相同资源时：

```
1. 检查缓存
2. 发现缓存命中（multimodal 的结果）
3. 日志显示：[CACHED|multimodal|mistralai/ministral-3b-2512]
4. 直接返回缓存结果，不再调用 LLM
```

## 建议

### 监控 Premium 失败率

建议监控以下指标：
- Premium 任务失败次数
- Premium 任务超时次数
- Premium 验证失败次数

如果失败率过高，可能需要：
1. 检查 premium 模型配置
2. 增加超时时间
3. 优化 prompt 以提高成功率

### 配置超时时间

如果 premium 模型经常超时，可以增加超时时间：

```yaml
# config.yaml
llm:
  premium_cache_timeout: 60.0  # 增加到 60 秒
```

---

**文档创建时间**：2026-02-10  
**状态**：✅ 已验证
