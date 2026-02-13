# 缓存坐标归一化修复

## 问题描述

在从缓存读取 `image_result` 时，遇到坐标验证错误：

```
dialogs.0.positionValue error, position[0] (min_x) must be in range [0.0, 1.0], got 65.0
```

### 根本原因

1. **旧缓存格式**：旧的缓存数据中，坐标是绝对像素值（如 `[65, 226, 636, 307]`）
2. **新验证规则**：`DialogItem` 模型要求坐标必须是归一化值（0.0-1.0 范围）
3. **缓存读取失败**：从缓存读取时，直接用 `ImageResult(**cached_payload)` 创建对象，触发验证失败

### 为什么会有旧格式的缓存？

在之前的代码中，可能存在以下情况：
- 某些流程直接缓存了绝对像素坐标
- 坐标归一化逻辑在缓存写入之后才执行
- 不同的代码路径使用了不同的坐标格式

## 解决方案

### 方案概述

在 `_get_screenshot_analysis_from_cache()` 函数中添加坐标修复逻辑：

1. 尝试直接加载缓存数据
2. 如果验证失败且错误是坐标范围问题：
   - 从缓存中获取图片尺寸（`image_dimensions` 类别）
   - 使用图片尺寸归一化坐标
   - 重新尝试创建 `ImageResult`
3. 如果修复失败，返回 `None` 触发新的分析

### 实现细节

```python
async def _get_screenshot_analysis_from_cache(content_url, session_id, scene, cache_service):
    """Get cached screenshot analysis result with coordinate repair."""
    
    # 1. 尝试直接加载
    cached_event = await cache_service.get_resource_category_last(...)
    if cached_event:
        cached_payload = cached_event.get("payload")
        try:
            cached_result = ImageResult(**cached_payload)
            return cached_result
        except Exception as e:
            # 2. 检查是否是坐标范围错误
            if "position" in str(e) and "must be in range [0.0, 1.0]" in str(e):
                # 3. 获取缓存的图片尺寸
                dimension_fetcher = get_dimension_fetcher()
                cached_dimensions = await dimension_fetcher.get_cached_dimensions(...)
                
                if cached_dimensions:
                    image_width, image_height = cached_dimensions
                    
                    # 4. 归一化坐标
                    for dialog in cached_payload.get("dialogs", []):
                        position = dialog.get("position", [])
                        if len(position) == 4:
                            x1, y1, x2, y2 = position
                            if any(coord > 1.0 for coord in position):
                                # 归一化到 0.0-1.0 范围
                                x1 = max(0.0, min(1.0, x1 / image_width))
                                y1 = max(0.0, min(1.0, y1 / image_height))
                                x2 = max(0.0, min(1.0, x2 / image_width))
                                y2 = max(0.0, min(1.0, y2 / image_height))
                                dialog["position"] = [x1, y1, x2, y2]
                    
                    # 5. 重新尝试创建对象
                    try:
                        cached_result = ImageResult(**cached_payload)
                        return cached_result
                    except Exception:
                        pass
            
            # 修复失败，返回 None
            return None
    return None
```

## 图片尺寸缓存

### ImageDimensionFetcher 服务

系统使用 `ImageDimensionFetcher` 服务来缓存图片尺寸：

```python
from app.services.image_dimension_fetcher import get_dimension_fetcher

dimension_fetcher = get_dimension_fetcher()

# 获取缓存的尺寸
cached_dimensions = await dimension_fetcher.get_cached_dimensions(
    url=content_url,
    cache_service=cache_service,
    session_id=session_id,
    scene=scene,
)

if cached_dimensions:
    image_width, image_height = cached_dimensions
```

### 缓存位置

图片尺寸缓存在 Redis 中，使用以下键：

- **Category**: `image_dimensions`
- **Resource**: 图片 URL
- **Payload**: `{"width": int, "height": int, "url": str}`

### 缓存时机

图片尺寸在以下时机被缓存：

1. **URL 模式**：后台任务异步获取并缓存
   ```python
   asyncio.create_task(
       dimension_fetcher.fetch_and_cache(
           url=content_url,
           cache_service=cache_service,
           session_id=session_id,
           scene=scene,
       )
   )
   ```

2. **Base64 模式**：下载图片时直接获取尺寸（不需要单独缓存）

## 坐标归一化流程

### 正常流程（新数据）

1. LLM 返回绝对像素坐标
2. `_repair_merge_step_bubble_bboxes()` 归一化坐标
3. 创建 `ImageResult` 对象（坐标已归一化）
4. 缓存 `ImageResult`（坐标已归一化）

### 修复流程（旧数据）

1. 从缓存读取 `image_result`（坐标是绝对像素值）
2. 验证失败（坐标 > 1.0）
3. 从缓存读取 `image_dimensions`
4. 使用图片尺寸归一化坐标
5. 重新验证并返回

## 向后兼容性

### 兼容旧缓存

✅ 自动修复旧格式的缓存数据
- 检测绝对像素坐标（> 1.0）
- 使用缓存的图片尺寸归一化
- 无需手动清除旧缓存

### 处理缺失的图片尺寸

如果缓存中没有图片尺寸：
- 无法修复旧坐标
- 返回 `None` 触发新的分析
- 新分析会生成正确的归一化坐标

### 新缓存格式

新写入的缓存数据：
- 坐标已经归一化（0.0-1.0）
- 直接通过验证
- 不需要修复

## 测试场景

### 场景 1：新缓存（归一化坐标）

**缓存数据：**
```json
{
  "dialogs": [
    {
      "position": [0.087, 0.169, 0.848, 0.230],
      "text": "Hello",
      "speaker": "user",
      "from_user": true
    }
  ]
}
```

**结果：** ✅ 直接加载成功

### 场景 2：旧缓存（绝对像素坐标）+ 有图片尺寸缓存

**缓存数据：**
```json
{
  "dialogs": [
    {
      "position": [65, 226, 636, 307],
      "text": "Hello",
      "speaker": "user",
      "from_user": true
    }
  ]
}
```

**图片尺寸缓存：** `750x1334`

**修复过程：**
1. 验证失败：`position[0] must be in range [0.0, 1.0], got 65.0`
2. 获取图片尺寸：`750x1334`
3. 归一化坐标：
   - `x1 = 65 / 750 = 0.087`
   - `y1 = 226 / 1334 = 0.169`
   - `x2 = 636 / 750 = 0.848`
   - `y2 = 307 / 1334 = 0.230`
4. 重新验证：✅ 成功

**结果：** ✅ 修复后加载成功

### 场景 3：旧缓存（绝对像素坐标）+ 无图片尺寸缓存

**缓存数据：** 同场景 2

**图片尺寸缓存：** 无

**结果：** ❌ 无法修复，返回 `None`，触发新分析

## 日志示例

### 成功修复

```
WARNING - Cached result for https://example.com/image.png has validation errors: position[0] (min_x) must be in range [0.0, 1.0], got 65.0
INFO - Attempting to repair coordinates using cached dimensions
INFO - Found cached dimensions: 750x1334
INFO - Successfully repaired and using cached result for https://example.com/image.png
```

### 无法修复（缺少尺寸）

```
WARNING - Cached result for https://example.com/image.png has validation errors: position[0] (min_x) must be in range [0.0, 1.0], got 65.0
INFO - Attempting to repair coordinates using cached dimensions
WARNING - No cached dimensions found for https://example.com/image.png, cannot repair coordinates
INFO - Will perform fresh analysis for https://example.com/image.png
```

### 直接加载（新缓存）

```
INFO - Using cached result for https://example.com/image.png
```

## 性能影响

### 缓存命中（新格式）

- 无额外开销
- 直接加载成功

### 缓存命中（旧格式，有尺寸）

- 额外的 Redis 查询（获取图片尺寸）
- 坐标归一化计算（O(n)，n = dialogs 数量）
- 总开销：< 10ms

### 缓存未命中或修复失败

- 触发新的 LLM 分析
- 与之前行为一致

## 相关文件

- `app/api/v1/predict.py`：`_get_screenshot_analysis_from_cache()` 函数
- `app/services/image_dimension_fetcher.py`：图片尺寸缓存服务
- `app/services/orchestrator.py`：`_repair_merge_step_bubble_bboxes()` 函数
- `app/models/v1_api.py`：`DialogItem` 模型验证

## 未来改进

### 自动清理旧缓存

可以添加一个后台任务，定期清理旧格式的缓存：

```python
async def cleanup_old_cache():
    """Clean up cache entries with absolute pixel coordinates."""
    # 遍历所有 image_result 缓存
    # 检查坐标格式
    # 删除旧格式的缓存
    pass
```

### 缓存版本控制

在缓存数据中添加版本字段：

```json
{
  "_version": "2.0",
  "_coordinate_format": "normalized",
  "dialogs": [...]
}
```

这样可以更明确地识别和处理不同版本的缓存数据。

## 总结

通过在缓存读取时添加坐标修复逻辑，我们实现了：

1. ✅ 向后兼容旧格式的缓存数据
2. ✅ 自动修复绝对像素坐标
3. ✅ 利用缓存的图片尺寸进行归一化
4. ✅ 优雅降级（无法修复时触发新分析）
5. ✅ 最小性能开销

这个修复确保了系统在处理旧缓存数据时的稳定性，同时保持了与新数据格式的兼容性。
