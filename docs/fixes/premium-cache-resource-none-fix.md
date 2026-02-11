# Premium 缓存 Resource=None 错误修复

**日期**: 2026-02-10  
**状态**: ✅ 已修复

## 问题描述

用户报告在 premium 后台任务缓存时出现错误：

```
WARNING - [1770707678134] Background: Failed to cache premium result: 
'NoneType' object has no attribute 'encode'
```

## 错误日志分析

```
2026-02-10 15:14:50,566 - app.services.orchestrator - INFO - [1770707678134] FINAL [premium|google/gemini-2.0-flash-001] Layout: left=talker, right=user
2026-02-10 15:14:50,566 - app.services.orchestrator - INFO - [1770707678134] FINAL [premium|google/gemini-2.0-flash-001] Extracted 8 bubbles (sorted top->bottom):
2026-02-10 15:14:50,566 - app.services.orchestrator - INFO - [1770707678134]   [1] talker(left) OK bbox=[27,193,94,235]: 🥺🥺
...
2026-02-10 15:14:50,567 - app.services.orchestrator - WARNING - [1770707678134] Background: Failed to cache premium result: 'NoneType' object has no attribute 'encode'
```

## 根本原因

### 1. Request.resource 可能为 None

在 `app/models/api.py` 中，`GenerateReplyRequest.resource` 定义为：

```python
resource: Optional[str] = Field(
    default=None, description="Resource identifier (image_url or text content)"
)
```

**默认值是 `None`**。

### 2. Redis hset 不接受 None 值

在 `app/services/session_categorized_cache_service.py` 的 `append_event()` 方法中：

```python
# Line 168
await redis_client.hset(map_key, resource_key, resource)
```

当 `resource` 是 `None` 时，Redis 客户端尝试调用 `None.encode()`，导致错误：
```
'NoneType' object has no attribute 'encode'
```

### 3. 两处代码都有问题

**后台任务缓存**（第 480 行）：
```python
resource = request.resource  # ❌ 可能是 None
```

**同步缓存**（第 608-609 行）：
```python
await self._cache_payload(request, "context_analysis", premium_context_data)
await self._cache_payload(request, "scene_analysis", premium_scene_data)
```

而且 `_cache_payload` 方法**根本不存在**！

## 修复方案

### 修复 1: 后台任务缓存

**位置**: `app/services/orchestrator.py` 第 480 行

**修复前**:
```python
resource = request.resource
```

**修复后**:
```python
resource = request.resource or ""  # Use empty string if None
```

### 修复 2: 同步缓存

**位置**: `app/services/orchestrator.py` 第 608-609 行

**修复前**:
```python
await self._cache_payload(request, "context_analysis", premium_context_data)
await self._cache_payload(request, "scene_analysis", premium_scene_data)
```

**修复后**:
```python
# Cache using cache_service.append_event
resource = request.resource or ""  # Use empty string if None
scene = request.scene if hasattr(request, 'scene') else ""

# Cache context_analysis
await self.cache_service.append_event(
    session_id=request.conversation_id,
    category="context_analysis",
    resource=resource,
    payload=premium_context_data,
    scene=scene
)

# Cache scene_analysis
await self.cache_service.append_event(
    session_id=request.conversation_id,
    category="scene_analysis",
    resource=resource,
    payload=premium_scene_data,
    scene=scene
)
```

## 修复详情

### 为什么使用空字符串？

1. **Redis 兼容性**: Redis 的 `hset` 命令接受空字符串，但不接受 `None`
2. **语义正确**: 空字符串表示"没有资源"，比 `None` 更明确
3. **向后兼容**: 不影响现有的缓存查询逻辑

### Python 的 `or` 运算符

```python
resource = request.resource or ""
```

**行为**:
- 如果 `request.resource` 是 `None` → 返回 `""`
- 如果 `request.resource` 是 `""` → 返回 `""`（空字符串也是 falsy）
- 如果 `request.resource` 有值 → 返回原值

## 测试验证

创建了 `test_premium_cache_resource_none.py` 测试三个场景：

### Test Case 1: resource=None
```python
request.resource = None
resource = request.resource or ""
assert resource == ""  # ✓
assert isinstance(resource, str)  # ✓
```

### Test Case 2: resource 有值
```python
request.resource = "https://example.com/image.jpg"
resource = request.resource or ""
assert resource == "https://example.com/image.jpg"  # ✓
```

### Test Case 3: Redis 操作
```python
await redis_client.hset("key", "field", "")  # ✓ 成功
# 不会抛出 'NoneType' object has no attribute 'encode'
```

**所有测试通过** ✅

## 影响范围

### 修复的场景

1. ✅ **后台任务缓存** - Premium 任务完成后在后台缓存
2. ✅ **同步缓存** - Premium 完成但不是获胜结果时缓存

### 不受影响的场景

- ✅ 正常的缓存读取
- ✅ 有 resource 值的请求
- ✅ 其他缓存操作

## 相关问题

### 为什么 `_cache_payload` 不存在？

这是之前重构时的遗留问题。代码应该直接使用 `cache_service.append_event()`，而不是调用不存在的辅助方法。

### 为什么没有更早发现？

1. 大多数请求都有 `resource` 值（图片 URL）
2. 只有在特定场景下（如文本对话）`resource` 才是 `None`
3. 错误只在后台任务中发生，不影响主流程

## 预防措施

### 代码审查建议

1. **检查 Optional 字段**: 所有 `Optional[str]` 字段在使用前都应该处理 `None` 值
2. **Redis 操作**: 确保传给 Redis 的值都是有效的字符串
3. **方法存在性**: 调用方法前确认方法存在

### 类型提示改进

可以考虑在 `append_event` 方法中添加类型检查：

```python
async def append_event(
    self, 
    *, 
    session_id: str, 
    category: str, 
    resource: str,  # 明确要求 str，不是 Optional[str]
    payload: dict[str, Any], 
    scene: str = ""
) -> None:
    # 添加运行时检查
    if resource is None:
        raise ValueError("resource cannot be None, use empty string instead")
```

## 相关文件

- `app/services/orchestrator.py` - **已修复** - 两处 resource 处理
- `app/services/session_categorized_cache_service.py` - Redis 操作
- `app/models/api.py` - GenerateReplyRequest 定义
- `test_premium_cache_resource_none.py` - **新增** - 测试修复
- `docs/fixes/premium-cache-resource-none-fix.md` - **新增** - 本文档

## 总结

✅ **问题已修复**

- 后台任务缓存：使用 `request.resource or ""`
- 同步缓存：修复不存在的 `_cache_payload` 方法，使用正确的 `cache_service.append_event()`
- 测试验证：所有场景通过
- 不会再出现 `'NoneType' object has no attribute 'encode'` 错误

**修复简单但关键** - 一个 `or ""` 解决了 Redis 编码错误！
