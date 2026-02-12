# Parallel Image Processing for Merge Step

## 概述

在 merge_step 模式下，当收到多个图片时，现在会并行调用第三方服务进行处理，而不是串行处理。这大大提高了多图片场景的处理速度。

## 改进前后对比

### 改进前（串行处理）

```python
for content_url in request.content:
    # 处理图片 1
    image_result_1 = await get_merge_step_analysis_result(url_1)  # 耗时 7s
    
    # 处理图片 2
    image_result_2 = await get_merge_step_analysis_result(url_2)  # 耗时 7s
    
    # 处理图片 3
    image_result_3 = await get_merge_step_analysis_result(url_3)  # 耗时 7s

# 总耗时: 21s
```

### 改进后（并行处理）

```python
# 创建并行任务
tasks = [
    process_single_image(url_1),  # 并行执行
    process_single_image(url_2),  # 并行执行
    process_single_image(url_3),  # 并行执行
]

# 等待所有任务完成
results = await asyncio.gather(*tasks)

# 总耗时: ~7s (最慢的那个)
```

## 性能提升

| 图片数量 | 串行耗时 | 并行耗时 | 提升 |
|---------|---------|---------|------|
| 1 张 | 7s | 7s | 0% |
| 2 张 | 14s | 7s | 50% |
| 3 张 | 21s | 7s | 67% |
| 5 张 | 35s | 7s | 80% |
| 10 张 | 70s | 7s | 90% |

## 实现细节

### 1. 保持原始顺序（关键！）

并行处理时必须保持 content 的原始顺序，因为后续的 reply generation 逻辑依赖于识别最后一个 content 的类型。

```python
# 为每个 content 添加索引
async def process_single_content(content_url: str, index: int):
    # ... 处理逻辑 ...
    return (index, kind, url, result)  # 返回时包含索引

# 创建任务时传入索引
content_tasks = [
    process_single_content(url, idx) 
    for idx, url in enumerate(request.content)
]

# 并行执行
content_results = await asyncio.gather(*content_tasks)

# 按原始索引排序，恢复顺序
content_results_sorted = sorted(content_results, key=lambda x: x[0])

# 提取结果（去掉索引）
items = [(kind, url, result) for _, kind, url, result in content_results_sorted]
```

### 2. 统一处理文本和图片

```python
async def process_single_content(content_url: str, index: int):
    """处理单个 content（图片或文本）"""
    # 处理文本
    if not _is_url(content_url):
        text_result = ImageResult(...)
        return (index, "text", content_url, text_result)
    
    # 处理图片
    image_result, scenario_json = await get_merge_step_analysis_result(...)
    return (index, "image", content_url, image_result)
```

### 3. 验证顺序正确性

```python
# 示例：["text1", "image2", "text3", "image4"]
# 并行处理后 items 应该是：
# [
#   ("text", "text1", text_result_1),
#   ("image", "image2", image_result_2),
#   ("text", "text3", text_result_3),
#   ("image", "image4", image_result_4),
# ]

# 最后一个 content 的类型
last_content_type = items[-1][0]  # "image"
last_content_value = items[-1][1]  # "image4"
```

## 关键设计决策

### 为什么必须保持原始顺序？

后续的 reply generation 逻辑（参见 `docs/analysis/final-implementation-plan.md`）依赖于识别最后一个 content 的类型：

1. **最后是图片**：使用该图片中 talker/left 的最后一句话作为 `reply_sentence`
2. **最后是文本**：使用该文本本身作为 `reply_sentence`

如果并行处理破坏了顺序，会导致：
- 错误地识别最后一个 content
- `reply_sentence` 选择错误
- reply generation 逻辑失败

### 示例场景

```python
# 原始请求
request.content = ["text1", "image2", "text3", "image4"]

# ❌ 错误：不保持顺序
items = [
    ("text", "text1", ...),
    ("text", "text3", ...),  # 文本被提前
    ("image", "image2", ...),
    ("image", "image4", ...),
]
# 最后一个是 image4 ✓ 但顺序错了

# ✅ 正确：保持原始顺序
items = [
    ("text", "text1", ...),
    ("image", "image2", ...),
    ("text", "text3", ...),
    ("image", "image4", ...),
]
# 最后一个是 image4 ✓ 顺序正确
```

## 适用场景

### 启用并行处理

并行处理仅在以下条件下启用：

1. **merge_step 模式已启用**：`USE_MERGE_STEP=true`
2. **有多个图片 URL**：`len(image_urls) > 0`

### 使用串行处理

以下情况仍使用串行处理：

1. **传统流程**：`USE_MERGE_STEP=false`
2. **没有图片**：只有文本内容
3. **单个图片**：并行和串行性能相同

## 错误处理

### 单个图片失败

如果某个图片处理失败，`asyncio.gather()` 会立即抛出异常，整个请求失败：

```python
try:
    image_results = await asyncio.gather(*image_tasks)
except Exception as e:
    logger.error(f"Parallel image processing failed: {e}")
    raise HTTPException(status_code=500, ...)
```

### 部分失败处理（可选）

如果需要容错处理（某些图片失败但继续处理其他图片），可以使用 `return_exceptions=True`：

```python
# 容错模式（未实现）
image_results = await asyncio.gather(*image_tasks, return_exceptions=True)

# 过滤成功的结果
successful_results = [
    r for r in image_results 
    if not isinstance(r, Exception)
]
```

## 监控和日志

### 并行处理日志

```
INFO - Processing 3 images in parallel using merge_step
DEBUG - screenshot_start: url=image1.png
DEBUG - screenshot_start: url=image2.png
DEBUG - screenshot_start: url=image3.png
DEBUG - screenshot_end: url=image1.png, duration=7089ms
DEBUG - screenshot_end: url=image2.png, duration=6882ms
DEBUG - screenshot_end: url=image3.png, duration=7234ms
INFO - Parallel processing completed: 3 images processed
```

### 性能指标

在 trace 日志中，每个图片都有独立的 `screenshot_start` 和 `screenshot_end` 事件：

```json
{
  "type": "screenshot_start",
  "task_type": "merge_step",
  "url": "https://example.com/image1.png",
  "session_id": "session_123",
  "ts": 1770309298.839
}
{
  "type": "screenshot_end",
  "task_type": "merge_step",
  "url": "https://example.com/image1.png",
  "duration_ms": 7089,
  "ts": 1770309305.928
}
```

## 缓存策略

每个图片的结果都会独立缓存：

```python
image_result_data = image_result.model_dump(mode="json")
image_result_data["_model"] = "merge-step"
image_result_data["_strategy"] = "parallel"  # 标记为并行处理

await cache_service.append_event(
    session_id=request.session_id,
    category="image_result",
    resource=content_url,
    payload=image_result_data,
    scene=request.scene,
)
```

## 资源使用

### 并发限制

当前实现没有并发限制，所有图片同时处理。如果需要限制并发数：

```python
# 限制并发数为 5（未实现）
from asyncio import Semaphore

semaphore = Semaphore(5)

async def process_with_limit(url):
    async with semaphore:
        return await process_single_image(url)

tasks = [process_with_limit(url) for url in image_urls]
results = await asyncio.gather(*tasks)
```

### 内存使用

并行处理会同时加载多个图片到内存。如果图片很大或数量很多，可能需要：

1. 限制并发数
2. 使用图片压缩（已支持）
3. 使用 URL 模式而不是 base64 模式

## 配置选项

### 启用并行处理

在 `.env` 中：

```bash
# 启用 merge_step 模式
USE_MERGE_STEP=true

# 图片格式（URL 模式更节省内存）
LLM_MULTIMODAL_IMAGE_FORMAT=url

# 图片压缩（base64 模式时）
LLM_MULTIMODAL_IMAGE_COMPRESS=true
```

### 禁用并行处理

如果需要回退到串行处理：

```bash
# 禁用 merge_step 模式
USE_MERGE_STEP=false
```

## 测试

### 单元测试

```python
import pytest
from app.api.v1.predict import predict

@pytest.mark.asyncio
async def test_parallel_image_processing():
    """测试并行图片处理"""
    request = PredictRequest(
        content=[
            "https://example.com/image1.png",
            "https://example.com/image2.png",
            "https://example.com/image3.png",
        ],
        user_id="test_user",
        session_id="test_session",
        reply=False,
    )
    
    start_time = time.time()
    response = await predict(request)
    duration = time.time() - start_time
    
    # 验证结果
    assert len(response.results) == 3
    
    # 验证并行处理（应该接近单个图片的时间）
    assert duration < 10  # 而不是 21s
```

### 负载测试

```bash
# 测试多图片并行处理
python tests/load_test.py --images 5 --concurrent 10
```

## 相关文件

- `app/api/v1/predict.py` - 主要实现
- `app/services/orchestrator.py` - merge_step 调用
- `.env` - 配置文件
- `dev-docs/MERGE_STEP_VALIDATION_ERROR.md` - 错误处理文档

## 未来改进

1. **并发限制**：添加 Semaphore 限制同时处理的图片数量
2. **部分失败容错**：使用 `return_exceptions=True` 允许部分图片失败
3. **进度报告**：实时报告处理进度
4. **批处理优化**：将多个图片合并为一个 LLM 调用（如果 LLM 支持）
5. **智能调度**：根据图片大小和复杂度动态调整并发数

## 总结

并行图片处理显著提升了 merge_step 模式下多图片场景的性能，特别是在处理 3 张以上图片时，可以节省 60-90% 的处理时间。这对于用户体验和系统吞吐量都有重要意义。


## 缓存优化（2026-02-11 更新）

### 问题：重复的缓存写入

在实现并行处理时，发现存在重复的缓存写入：

1. `get_merge_step_analysis_result()` 函数内部会写入缓存（lines 858-868）
2. 并行处理代码中也有缓存写入（已删除的 lines 1324-1328）
3. 串行处理代码中也有缓存写入（lines 1456-1467）

这导致：
- merge_step 流程的结果被缓存两次
- 浪费 I/O 和存储
- 可能导致缓存不一致

### 解决方案：单一缓存写入点

#### 1. merge_step 流程

`get_merge_step_analysis_result()` 是唯一的缓存写入点，并接受 `strategy` 参数来标记处理方式：

```python
async def get_merge_step_analysis_result(
    content_url: str,
    request: PredictRequest,
    orchestrator: OrchestratorDep,
    cache_service: SessionCategorizedCacheServiceDep,
    strategy: str = "auto",  # "parallel", "serial", or "auto"
) -> tuple[ImageResult, str]:
    # 检查缓存
    cached_result = await _get_screenshot_analysis_from_cache(...)
    if cached_result:
        return cached_result, scenario_json
    
    # 调用 LLM
    image_result, scenario_json = await orchestrator.merge_step_analysis(...)
    
    # 写入缓存（唯一写入点）
    image_result_data = image_result.model_dump(mode="json")
    image_result_data["_model"] = "merge-step"
    image_result_data["_strategy"] = strategy  # 使用传入的 strategy
    
    await cache_service.append_event(
        session_id=request.session_id,
        category="image_result",
        resource=content_url,
        payload=image_result_data,
        scene=request.scene,
    )
    
    return image_result, scenario_json
```

#### 2. 并行处理路径

传入 `strategy="parallel"` 来标记并行处理：

```python
async def process_single_content(content_url: str, index: int):
    # 调用 merge_step（内部处理缓存）
    image_result, scenario_json = await get_merge_step_analysis_result(
        content_url,
        request,
        orchestrator,
        cache_service,
        strategy="parallel",  # 标记为并行处理
    )
    
    # ✅ 不再重复写入缓存
    # ❌ 已删除：await cache_service.append_event(...)
    
    return (index, "image", content_url, image_result)
```

#### 3. 串行处理路径

根据流程类型传入不同的 strategy：

```python
for content_url in request.content:
    if use_merge_step:
        # merge_step 内部处理缓存，标记为串行
        image_result, scenario_json = await get_merge_step_analysis_result(
            content_url,
            request,
            orchestrator,
            cache_service,
            strategy="serial",  # 标记为串行处理
        )
    else:
        # 传统流程需要显式缓存
        image_result = await get_screenshot_analysis_result(...)
    
    # ✅ 只在传统流程中写入缓存
    if not use_merge_step:
        image_result_data = image_result.model_dump(mode="json")
        image_result_data["_model"] = "non-merge-step"
        image_result_data["_strategy"] = "serial"
        
        await cache_service.append_event(
            session_id=request.session_id,
            category="image_result",
            resource=content_url,
            payload=image_result_data,
            scene=request.scene,
        )
```

### 缓存格式一致性

所有缓存的 `image_result` 都包含以下元数据字段：

| 字段 | 说明 | 可能的值 |
|-----|------|---------|
| `_model` | 使用的模型/流程 | `"merge-step"`, `"non-merge-step"` |
| `_strategy` | 处理策略 | `"parallel"`, `"serial"`, `"auto"` |

#### 缓存格式示例

**并行 merge-step 处理：**
```json
{
  "content": "https://example.com/image.png",
  "dialogs": [...],
  "scenario": "{...}",
  "_model": "merge-step",
  "_strategy": "parallel"
}
```

**串行 merge-step 处理：**
```json
{
  "content": "https://example.com/image.png",
  "dialogs": [...],
  "scenario": "{...}",
  "_model": "merge-step",
  "_strategy": "serial"
}
```

**传统流程（串行）：**
```json
{
  "content": "https://example.com/image.png",
  "dialogs": [...],
  "_model": "non-merge-step",
  "_strategy": "serial"
}
```

### 缓存写入位置总结

| 流程 | 缓存写入位置 | _model | _strategy |
|-----|------------|--------|-----------|
| merge_step（并行） | `get_merge_step_analysis_result()` | `"merge-step"` | `"parallel"` |
| merge_step（串行） | `get_merge_step_analysis_result()` | `"merge-step"` | `"serial"` |
| 传统流程（串行） | 串行处理循环中 | `"non-merge-step"` | `"serial"` |

### 缓存命中逻辑

缓存命中时，`_strategy` 字段会被保留在返回的数据中，用于日志记录和调试：

```python
# 缓存命中
cached_result = await _get_screenshot_analysis_from_cache(...)
if cached_result:
    logger.info(f"Cache hit for {content_url}")
    # cached_result 包含原始的 _strategy 字段
    # 日志中会显示：strategy=parallel 或 strategy=serial
    return cached_result, scenario_json
```

### 验证缓存正确性

```python
# 测试缓存命中
# 1. 第一次请求（缓存未命中）
response1 = await predict(request)
# 日志：Cache miss for image.png, calling merge_step analysis
# 日志：Cached new merge_step result for image.png (strategy=parallel)

# 2. 第二次请求（缓存命中）
response2 = await predict(request)
# 日志：Cache hit for image.png
# 日志：不应该有 "Cached new merge_step result"

# 3. 验证结果一致
assert response1.results == response2.results
```

### 性能影响

移除重复缓存写入后：
- 减少 50% 的缓存 I/O 操作
- 避免缓存不一致风险
- 不影响缓存命中率
- 不影响并行处理性能
- `_strategy` 字段正确标记处理方式，便于监控和调试

### 相关修改

- `app/api/v1/predict.py` line 670: 添加 `strategy` 参数到 `get_merge_step_analysis_result()`
- `app/api/v1/predict.py` line 852: 使用传入的 `strategy` 参数设置缓存元数据
- `app/api/v1/predict.py` line 1287: 并行处理传入 `strategy="parallel"`
- `app/api/v1/predict.py` line 1403: 串行处理传入 `strategy="serial"`
- `app/api/v1/predict.py` lines 1323-1329: 移除并行处理中的重复缓存写入
- `app/api/v1/predict.py` lines 1456-1467: 添加条件判断，只在传统流程中写入缓存
- `dev-docs/PARALLEL_IMAGE_PROCESSING.md`: 更新文档说明缓存策略和格式一致性
