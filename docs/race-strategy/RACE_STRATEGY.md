# 最终竞速策略说明

## 核心原则

**先到先得（First Valid Wins）**

- 哪个模型先返回有效结果，就用哪个
- 不等待其他模型
- 最快响应用户

## 详细逻辑

### 1. 并发启动

```python
multimodal_task = asyncio.create_task(call_multimodal_llm())
premium_task = asyncio.create_task(call_premium_llm())
```

两个任务同时开始，互不阻塞。

---

### 2. 等待第一个有效结果

```python
while pending and winning_result is None:
    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
    
    for task in done:
        strategy, result = await task
        
        if result and validator(result):
            winning_result = result
            winning_strategy = strategy
            break  # 立即返回，不再等待
```

**关键点**：
- 使用 `asyncio.FIRST_COMPLETED` 等待任意一个完成
- 验证结果是否有效
- 找到第一个有效结果后**立即返回**
- 不管是 multimodal 还是 premium

---

### 3. 返回值

```python
return (
    winning_strategy,           # "multimodal" 或 "premium"
    winning_result,             # 用于当前响应的结果
    premium_task_or_result      # Task（未完成）或 Result（已完成）
)
```

**第三个返回值的含义**：
- 如果 premium 已完成：返回 premium 结果对象
- 如果 premium 未完成：返回 premium Task 对象

---

## 场景分析

### 场景 1: Multimodal 先完成（2秒），Premium 慢（4秒）

```
T=0s:  启动两个任务
T=2s:  Multimodal 完成 ✓ → 立即返回
       winning_strategy = "multimodal"
       winning_result = multimodal_result
       premium_task_or_result = premium_task (还在运行)
T=2s:  开始生成回复
T=4s:  Premium 完成 ✓ → 后台缓存
```

**结果**：
- ✅ 用户在 2秒 得到响应
- ✅ Premium 在 4秒 完成并缓存
- ✅ 下次请求使用缓存的 premium 结果

---

### 场景 2: Premium 先完成（3秒），Multimodal 慢（5秒）

```
T=0s:  启动两个任务
T=3s:  Premium 完成 ✓ → 立即返回
       winning_strategy = "premium"
       winning_result = premium_result
       premium_task_or_result = premium_result (已完成)
T=3s:  开始生成回复
T=5s:  Multimodal 完成（被忽略）
```

**结果**：
- ✅ 用户在 3秒 得到响应
- ✅ 使用最高质量的 premium 结果
- ✅ Premium 结果同步缓存

---

### 场景 3: Multimodal 先完成（2秒），Premium 稍后完成（2.5秒）

```
T=0s:  启动两个任务
T=2s:  Multimodal 完成 ✓ → 立即返回
       winning_strategy = "multimodal"
       winning_result = multimodal_result
       premium_task_or_result = premium_task (还在运行)
T=2s:  开始生成回复
T=2.5s: Premium 完成 ✓ → 后台缓存
```

**关键点**：
- ⚠️ 即使 premium 只慢 0.5秒，也不等待
- ✅ 优先快速响应用户
- ✅ Premium 结果后台缓存供下次使用

---

### 场景 4: Multimodal 失败，Premium 成功

```
T=0s:  启动两个任务
T=2s:  Multimodal 完成 ✗ (无效)
T=2s:  继续等待 premium
T=4s:  Premium 完成 ✓ → 返回
       winning_strategy = "premium"
       winning_result = premium_result
```

**结果**：
- ✅ 容错机制生效
- ✅ 用户在 4秒 得到响应
- ✅ 使用 premium 结果

---

### 场景 5: 两者都失败

```
T=0s:  启动两个任务
T=2s:  Multimodal 完成 ✗ (无效)
T=4s:  Premium 完成 ✗ (无效)
T=4s:  抛出 ValueError
```

**结果**：
- ❌ 没有有效结果
- ❌ 不生成回复
- ❌ 返回错误给用户

---

## 与之前方案的对比

### 方案 A: 总是等待 Premium（已废弃）

```python
# 等待两个都完成
multimodal_result = await multimodal_task
premium_result = await premium_task

# 优先使用 premium
if premium_valid:
    return premium_result
else:
    return multimodal_result
```

**问题**：
- ❌ 总是等待较慢的模型
- ❌ 响应时间 = max(multimodal_time, premium_time)
- ❌ 用户体验差

---

### 方案 B: 先到先得（当前方案）

```python
# 等待第一个有效结果
while pending and winning_result is None:
    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
    
    if valid_result_found:
        return immediately
```

**优势**：
- ✅ 响应时间 = min(multimodal_time, premium_time)
- ✅ 快速响应用户
- ✅ Premium 后台缓存
- ✅ 最佳用户体验

---

## 性能对比

| 场景 | Multimodal | Premium | 方案A响应时间 | 方案B响应时间 | 提升 |
|------|-----------|---------|--------------|--------------|------|
| 1 | 2s ✓ | 4s ✓ | 4s | 2s | **50%** |
| 2 | 5s ✓ | 3s ✓ | 5s | 3s | **40%** |
| 3 | 2s ✓ | 2.5s ✓ | 2.5s | 2s | **20%** |
| 4 | 2s ✗ | 4s ✓ | 4s | 4s | 0% |
| 5 | 2s ✗ | 4s ✗ | 4s | 4s | 0% |

**平均提升**: 约 **30-40%** 响应时间减少

---

## 后台缓存机制

### 判断逻辑

```python
if isinstance(premium_result_or_task, asyncio.Task):
    # Premium 还在运行，后台缓存
    async def cache_premium_when_ready():
        _, premium_result = await premium_task
        # 缓存逻辑
    
    asyncio.create_task(cache_premium_when_ready())
else:
    # Premium 已完成，同步缓存
    await cache_service.set(...)
```

### 关键点

1. **提取信息**：在创建后台任务前提取 `resource` 和 `conversation_id`
2. **不依赖 request**：直接使用 cache service
3. **异常处理**：捕获所有异常，不影响主流程
4. **Fire and forget**：不等待后台任务完成

---

## 代码位置

### 竞速逻辑
- **文件**: `app/services/screenshot_parser.py`
- **方法**: `_race_multimodal_calls()`
- **行数**: ~340-460

### 后台缓存
- **文件**: `app/services/orchestrator.py`
- **方法**: `merge_step_analysis()`
- **行数**: ~470-520

---

## 监控指标

### 关键指标

1. **响应时间分布**
   ```python
   metrics.histogram("response_time_ms", duration)
   metrics.histogram("multimodal_time_ms", multimodal_duration)
   metrics.histogram("premium_time_ms", premium_duration)
   ```

2. **策略选择统计**
   ```python
   metrics.increment(f"race.winner.{winning_strategy}")
   # race.winner.multimodal
   # race.winner.premium
   ```

3. **后台缓存成功率**
   ```python
   metrics.increment("background_cache.success")
   metrics.increment("background_cache.failure")
   ```

### 日志关键字

```bash
# 查看竞速结果
grep "Using .* result for immediate response" logs/app.log

# 查看后台缓存
grep "Background: Premium result cached" logs/app.log

# 查看失败情况
grep "Both calls failed" logs/app.log
```

---

## 总结

### 核心优势

1. **快速响应** - 不等待较慢的模型
2. **智能缓存** - Premium 结果后台缓存
3. **容错机制** - 一个失败不影响另一个
4. **最佳体验** - 平均响应时间减少 30-40%

### 权衡

- ✅ 响应速度优先
- ⚠️ 可能使用较低质量的结果（如果 multimodal 先完成）
- ✅ 但下次请求会使用缓存的 premium 结果

### 适用场景

- ✅ 对响应时间敏感的应用
- ✅ 可以接受首次请求使用较低质量结果
- ✅ 后续请求使用高质量缓存结果
- ✅ 用户体验优先于单次质量
