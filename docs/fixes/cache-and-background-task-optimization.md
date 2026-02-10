# 缓存和后台任务优化完整指南

> **优化完成时间**：2026-02-10  
> **状态**：已完成并测试 ✅  
> **部署状态**：可以立即部署

## 目录

1. [概述](#概述)
2. [问题与解决方案](#问题与解决方案)
3. [技术实现](#技术实现)
4. [测试验证](#测试验证)
5. [使用指南](#使用指南)
6. [性能影响](#性能影响)

---

## 概述

本次优化解决了缓存日志缺少模型信息的问题，修复了 premium 后台任务的多个 bug，并添加了完整的后台任务管理系统。

### 完成的 5 项优化

1. ✅ **缓存日志增强** - 显示模型和策略信息
2. ✅ **Premium 后台任务修复** - 修复 3 个关键 bug
3. ✅ **后台任务管理系统** - 自动追踪和清理
4. ✅ **超时保护** - 防止任务无限等待
5. ✅ **Premium 日志增强** - 完整的执行日志

---

## 问题与解决方案

### 1. 缓存日志缺少模型信息

**问题**：
```
[1770693542722] merge_step [CACHED] Conversation: 6 messages
```
无法知道缓存结果是由哪个模型生成的。

**解决方案**：
在缓存 payload 中添加 `_model` 和 `_strategy` 元数据：

```python
context_data = context.model_dump(mode="json")
context_data["_model"] = llm_result.model
context_data["_strategy"] = winning_strategy
```

**效果**：
```
[1770693542722] merge_step [CACHED|multimodal|google/gemini-2.0-flash-exp:free] Conversation: 6 messages
```

---

### 2. Premium 后台任务的 Bug

**问题**：
1. ❌ 使用不存在的 `get_cache_service()` 函数
2. ❌ 使用错误的 `cache_service.set()` API
3. ❌ 访问可能失效的 `request` 对象

**修复**：

#### 修复 1：使用实例变量
```python
# 错误
from app.services.cache_service import get_cache_service
cache_service = get_cache_service()

# 正确
cache_service = self.cache_service
```

#### 修复 2：使用正确的 API
```python
# 错误
await cache_service.set(category="context_analysis", resource=resource, data=data)

# 正确
await cache_service.append_event(
    session_id=conversation_id,
    category="context_analysis",
    resource=resource,
    payload=data,
    scene=scene
)
```

#### 修复 3：在闭包中捕获参数
```python
# 在创建闭包前捕获所有需要的值
resource = request.resource
conversation_id = request.conversation_id
scene = request.scene if hasattr(request, 'scene') else ""
cache_service = self.cache_service

async def cache_premium_when_ready():
    # 使用闭包捕获的值，不依赖 request 对象
    await cache_service.append_event(...)
```

---

### 3. Premium 日志缺失

**问题**：
Premium 后台任务执行过程完全不可见，只有一条日志：
```
[1770693542722] Premium task still running, will cache in background
```

**解决方案**：
添加详细的进度日志和调用 `_log_merge_step_extraction`：

```python
async def cache_premium_when_ready():
    try:
        logger.info(f"[{conversation_id}] Background: Waiting for premium task to complete...")
        _, premium_result = await asyncio.wait_for(premium_result_or_task, timeout=timeout)
        
        if premium_result:
            logger.info(f"[{conversation_id}] Background: Premium task completed, processing result")
            premium_parsed = parse_json_with_markdown(premium_result.text)
            
            if validate_merge_step_result(premium_parsed):
                logger.info(f"[{conversation_id}] Background: Premium result is valid")
                
                # 调用详细日志方法
                self._log_merge_step_extraction(
                    session_id=conversation_id,
                    strategy="premium",
                    model=premium_result.model,
                    parsed_json=premium_parsed
                )
                
                # ... 缓存逻辑
                logger.info(f"[{conversation_id}] Background: Premium result cached successfully")
```

**效果**：
```
[1770693542722] Premium task still running, will cache in background
[1770693542722] Background: Waiting for premium task to complete...
[1770693542722] Background: Premium task completed, processing result
[1770693542722] Background: Premium result is valid
[1770693542722] Background: Logging premium extraction details
[1770693542722] merge_step [premium|anthropic/claude-3.5-sonnet] Participants: User='Zhang', Target='徐康'
[1770693542722] FINAL [premium|anthropic/claude-3.5-sonnet] Layout: left=talker, right=user
[1770693542722] FINAL [premium|anthropic/claude-3.5-sonnet] Extracted 6 bubbles (sorted top->bottom):
[1770693542722]   [1] talker(left) OK bbox=[100,200,350,250]: 真的假的
...
[1770693542722] Background: Premium result cached successfully
```

---

## 技术实现

### 后台任务管理系统

```python
class Orchestrator:
    def __init__(self, ...):
        # 任务追踪
        self._background_tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
    
    def _register_background_task(self, task: asyncio.Task, task_name: str) -> None:
        """注册任务并设置自动清理回调"""
        self._background_tasks.append(task)
        
        def on_task_done(t: asyncio.Task):
            try:
                self._background_tasks.remove(t)
            except ValueError:
                pass
        
        task.add_done_callback(on_task_done)
    
    async def shutdown(self, timeout: float = 30.0) -> None:
        """优雅关闭，等待或取消任务"""
        if self._background_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._background_tasks, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                for task in self._background_tasks:
                    if not task.done():
                        task.cancel()
    
    def get_background_task_count(self) -> int:
        """获取活跃任务数量"""
        return len(self._background_tasks)
```

### 超时保护

```python
async def cache_premium_when_ready():
    try:
        timeout = getattr(settings.llm, 'premium_cache_timeout', 30.0)
        _, premium_result = await asyncio.wait_for(
            premium_result_or_task,
            timeout=timeout
        )
        # ... 缓存逻辑
    except asyncio.TimeoutError:
        logger.warning(f"Premium task timeout after {timeout}s")
    except asyncio.CancelledError:
        logger.info("Premium caching cancelled")
    except Exception as e:
        logger.warning(f"Failed to cache premium result: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
```

### Premium 后台任务工作流程

```
时间线：
t=0.0s: 同时启动 multimodal 和 premium 任务
t=0.5s: multimodal 完成（快）
t=0.5s: 返回 multimodal 结果给用户 ← REQUEST 返回
t=0.5s: 创建后台任务等待 premium
t=2.0s: premium 完成（慢）
t=2.1s: 后台任务缓存 premium 结果
```

**优点**：
- ✅ 用户获得快速响应
- ✅ Premium 结果被缓存供下次使用
- ✅ 不浪费已启动的 API 调用

---

## 测试验证

### 测试 1：缓存日志格式
```bash
python test_cache_model_logging.py
```
- ✅ 日志包含模型和策略信息
- ✅ 向后兼容旧缓存

### 测试 2：后台任务行为
```bash
python test_premium_background_task.py
```
- ✅ Multimodal 快速返回
- ✅ Premium 后台缓存
- ✅ 应用关闭时任务取消

### 测试 3：任务管理系统
```bash
python test_background_task_management.py
```
- ✅ 任务注册和自动清理
- ✅ 优雅关闭等待任务
- ✅ 超时保护防止挂起
- ✅ 关闭超时取消任务

### 测试 4：Premium 日志
```bash
python test_premium_logging.py
```
- ✅ 完整的进度日志
- ✅ 超时日志
- ✅ 错误日志和堆栈

---

## 使用指南

### 应用启动
```python
from app.core.container import get_container

container = get_container()
orchestrator = container.create_orchestrator()
```

### 应用关闭
```python
# 在应用关闭时调用
await orchestrator.shutdown(timeout=30.0)
```

### 监控任务
```python
# 查询活跃任务数量
count = orchestrator.get_background_task_count()
logger.info(f"Active background tasks: {count}")

# 定期检查
if count > 10:
    logger.warning(f"High number of background tasks: {count}")
```

### 配置超时时间（可选）
```yaml
# config.yaml
llm:
  premium_cache_timeout: 30.0  # Premium 任务超时（秒）
```

---

## 性能影响

### 内存
- **增加**：每个后台任务约 1KB
- **影响**：可忽略（通常 0-5 个活跃任务）

### CPU
- **增加**：任务注册和清理的开销
- **影响**：可忽略（O(1) 操作）

### 日志
- **增加**：Premium 任务约 10 条额外日志
- **影响**：可接受（便于调试）

### 响应时间
- **主请求**：无影响（后台任务不阻塞）
- **关闭时间**：增加最多 30 秒（等待后台任务）

---

## 修改的文件

### `app/services/orchestrator.py`

1. **第 130-133 行**：添加后台任务管理属性
2. **第 334-343 行**：修改缓存命中时的日志输出
3. **第 475-560 行**：修复和优化 premium 后台任务
4. **第 562-585 行**：修复同步 premium 缓存
5. **第 641-658 行**：在主要结果缓存中添加元数据
6. **第 1495-1550 行**：添加后台任务管理方法

---

## 向后兼容性

- ✅ 旧缓存数据兼容（显示 `unknown` 作为模型）
- ✅ 不影响现有 API
- ✅ 新方法是可选的
- ✅ 默认配置适用于大多数场景

---

## 部署建议

### 立即可部署 ✅
- 所有修改向后兼容
- 无需数据库迁移
- 无需配置更改（使用默认值）

### 可选配置
```yaml
# config.yaml
llm:
  premium_cache_timeout: 30.0  # Premium 任务超时（秒）
```

---

## 总结

本次优化显著提升了系统的：
- ✅ **可观测性**：完整的模型信息和执行日志
- ✅ **可靠性**：正确的缓存逻辑和错误处理
- ✅ **健壮性**：超时保护和任务管理
- ✅ **可维护性**：清晰的任务追踪和调试能力

所有修改都经过充分测试，向后兼容，可以安全部署到生产环境。

---

## 相关文档

- 测试脚本：`test_cache_model_logging.py`, `test_premium_background_task.py`, `test_background_task_management.py`, `test_premium_logging.py`
- 修改文件：`app/services/orchestrator.py`
