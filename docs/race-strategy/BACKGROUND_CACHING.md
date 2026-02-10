# 后台缓存解决方案

## 问题描述

### 场景：Reply 先于 Premium 完成

```
T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✓ → 返回
T=2s:  开始 reply 生成（基于 multimodal）
T=3s:  Reply 完成 → HTTP 响应返回给用户 ✅
T=3s:  FastAPI 清理请求上下文
T=4s:  Premium 完成 ✓ → 后台任务尝试缓存
T=4s:  ❌ request 对象已失效！
```

### 核心问题

**后台任务依赖已失效的 request 对象**

```python
# ❌ 错误的做法
async def cache_premium_when_ready():
    _, premium_result = await premium_task
    # request 对象可能已经失效
    await self._cache_payload(request, "context_analysis", data)
```

**为什么会失效？**

1. **HTTP 请求生命周期**：
   - FastAPI 的 request 对象绑定到 HTTP 请求
   - 响应返回后，请求上下文被清理
   - 后台任务可能在请求结束后才执行

2. **异步任务独立性**：
   - `asyncio.create_task()` 创建的任务独立于请求
   - 任务可能在请求结束后继续运行
   - 访问已清理的对象会导致错误

---

## 解决方案

### 方案 1: 提取必要信息（当前实现）

**核心思想**：在创建后台任务前，提取所有需要的信息

```python
# ✅ 正确的做法
if isinstance(premium_result_or_task, asyncio.Task):
    # 1. 提取必要信息（在 request 失效前）
    resource = request.resource
    conversation_id = request.conversation_id
    
    async def cache_premium_when_ready():
        try:
            _, premium_result = await premium_result_or_task
            
            # 2. 直接使用 cache service（不依赖 request）
            from app.services.cache_service import get_cache_service
            cache_service = get_cache_service()
            
            # 3. 使用提取的信息进行缓存
            await cache_service.set(
                category="context_analysis",
                resource=resource,  # 使用提取的值
                data=premium_context.model_dump()
            )
        except Exception as e:
            logger.warning(f"Failed to cache: {e}")
    
    # 4. 启动后台任务
    asyncio.create_task(cache_premium_when_ready())
```

**优点**：
- ✅ 不依赖 request 对象
- ✅ 使用值拷贝，不受请求生命周期影响
- ✅ 直接调用 cache service

**缺点**：
- ⚠️ 需要手动提取所有必要信息
- ⚠️ 如果 cache service 需要更多信息，需要修改代码

---

### 方案 2: 使用 BackgroundTasks（备选）

FastAPI 提供了 `BackgroundTasks` 来处理这种情况：

```python
from fastapi import BackgroundTasks

async def merge_step_analysis(
    self,
    request: GenerateReplyRequest,
    background_tasks: BackgroundTasks,  # 注入
    ...
):
    # ... race logic ...
    
    if isinstance(premium_result_or_task, asyncio.Task):
        # 使用 BackgroundTasks
        background_tasks.add_task(
            cache_premium_result,
            premium_task=premium_result_or_task,
            resource=request.resource,
            conversation_id=request.conversation_id
        )
```

**优点**：
- ✅ FastAPI 原生支持
- ✅ 自动管理任务生命周期
- ✅ 在响应发送后执行

**缺点**：
- ⚠️ 需要修改函数签名
- ⚠️ 需要在调用链中传递 BackgroundTasks
- ⚠️ 当前架构不支持（orchestrator 不是直接的 endpoint）

---

### 方案 3: 使用消息队列（未来考虑）

对于更复杂的场景，可以使用消息队列：

```python
# 发送到队列
await redis_queue.enqueue({
    "task": "cache_premium_result",
    "premium_task_id": task_id,
    "resource": request.resource,
    "conversation_id": request.conversation_id
})

# Worker 处理
async def worker():
    while True:
        task = await redis_queue.dequeue()
        await process_task(task)
```

**优点**：
- ✅ 完全解耦
- ✅ 可重试
- ✅ 可监控

**缺点**：
- ⚠️ 增加系统复杂度
- ⚠️ 需要额外的基础设施（Redis/RabbitMQ）
- ⚠️ 对当前场景过度设计

---

## 当前实现详解

### 关键代码

```python
# app/services/orchestrator.py

if isinstance(premium_result_or_task, asyncio.Task):
    # 步骤 1: 提取信息（在 request 失效前）
    resource = request.resource
    conversation_id = request.conversation_id
    
    async def cache_premium_when_ready():
        try:
            # 步骤 2: 等待 premium 完成
            _, premium_result = await premium_result_or_task
            
            if premium_result:
                # 步骤 3: 解析和验证
                premium_parsed = parse_json_with_markdown(premium_result.text)
                if validate_merge_step_result(premium_parsed):
                    premium_context, premium_scene = merge_adapter.to_results(premium_parsed)
                    
                    # 步骤 4: 直接使用 cache service
                    from app.services.cache_service import get_cache_service
                    cache_service = get_cache_service()
                    
                    # 步骤 5: 缓存（使用提取的值）
                    await cache_service.set(
                        category="context_analysis",
                        resource=resource,  # ✅ 使用提取的值
                        data=premium_context.model_dump()
                    )
                    
                    await cache_service.set(
                        category="scene_analysis",
                        resource=resource,  # ✅ 使用提取的值
                        data=premium_scene.model_dump()
                    )
                    
                    logger.info(f"[{conversation_id}] Background: Premium cached")
        
        except asyncio.CancelledError:
            # 任务被取消（例如服务器关闭）
            logger.info(f"[{conversation_id}] Background: Caching cancelled")
        
        except Exception as e:
            # 其他错误（不影响主流程）
            logger.warning(f"[{conversation_id}] Background: Failed to cache: {e}")
    
    # 步骤 6: 启动后台任务（fire and forget）
    asyncio.create_task(cache_premium_when_ready())
```

---

## 异常处理

### 1. 任务取消

```python
except asyncio.CancelledError:
    logger.info("Background: Caching cancelled")
```

**何时发生**：
- 服务器关闭
- 应用重启
- 手动取消任务

**处理方式**：
- 记录日志
- 不抛出异常
- 优雅退出

---

### 2. 缓存失败

```python
except Exception as e:
    logger.warning(f"Background: Failed to cache: {e}")
```

**何时发生**：
- Cache service 不可用
- 网络错误
- 数据格式错误

**处理方式**：
- 记录警告日志
- 不影响主流程
- 下次请求会重新生成

---

## 测试场景

### 场景 1: Premium 在 Reply 前完成

```
T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✓
T=3s:  Premium 完成 ✓ → 直接缓存（同步）
T=4s:  Reply 完成 → 返回给用户
```

**结果**：✅ Premium 已缓存，不需要后台任务

---

### 场景 2: Premium 在 Reply 后完成

```
T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✓
T=3s:  Reply 完成 → 返回给用户
T=3s:  HTTP 请求结束
T=4s:  Premium 完成 ✓ → 后台任务缓存
```

**结果**：✅ 后台任务使用提取的信息，成功缓存

---

### 场景 3: Premium 失败

```
T=0s:  启动 multimodal 和 premium
T=2s:  Multimodal 完成 ✓
T=3s:  Reply 完成 → 返回给用户
T=4s:  Premium 失败 ✗ → 后台任务记录警告
```

**结果**：✅ 不影响用户体验，记录日志

---

## 性能影响

### 内存使用

**提取的信息**：
- `resource`: 字符串（URL），约 100-200 bytes
- `conversation_id`: 字符串（UUID），约 36 bytes

**总计**：约 200 bytes per request

**影响**：可忽略不计

---

### 并发性

**后台任务数量**：
- 每个使用 multimodal 的请求：1 个后台任务
- 峰值 QPS 100：最多 100 个并发后台任务

**影响**：
- 后台任务不阻塞主流程
- 使用异步 I/O，资源消耗低
- Cache service 需要支持并发

---

## 监控建议

### 关键指标

1. **后台缓存成功率**
   ```python
   metrics.increment("background_cache.success")
   metrics.increment("background_cache.failure")
   ```

2. **Premium 完成时间分布**
   ```python
   metrics.histogram("premium.duration_ms", duration)
   ```

3. **后台任务数量**
   ```python
   metrics.gauge("background_tasks.count", active_count)
   ```

### 日志关键字

搜索这些日志来监控后台缓存：

```bash
# 成功
grep "Background: Premium result cached successfully" logs/app.log

# 失败
grep "Background: Failed to cache premium result" logs/app.log

# 取消
grep "Background: Premium caching cancelled" logs/app.log
```

---

## 总结

### 核心解决方案

1. **提取必要信息**：在 request 失效前提取
2. **直接使用 cache service**：不依赖 request 对象
3. **异常处理**：捕获所有异常，不影响主流程
4. **Fire and forget**：后台任务独立运行

### 优势

- ✅ 快速响应用户（不等待 premium）
- ✅ 后台缓存 premium 结果
- ✅ 不依赖请求生命周期
- ✅ 异常不影响主流程

### 注意事项

- ⚠️ 后台任务可能失败（记录日志）
- ⚠️ Cache service 需要支持并发
- ⚠️ 服务器关闭时任务可能丢失（可接受）
