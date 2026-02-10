# 图片尺寸缓存功能

## 概述

当使用 URL 模式（`MULTIMODAL_IMAGE_FORMAT=url`）时，系统不会下载图片来获取尺寸，而是使用占位符尺寸（1080x1920）。为了在后续请求中使用真实尺寸，系统会在后台异步下载图片获取真实尺寸并缓存。

## 功能特点

### 1. 非阻塞设计
- 主请求流程不等待图片下载
- 使用占位符尺寸立即返回响应
- 后台任务异步获取真实尺寸

### 2. 智能缓存
- 首次请求：使用占位符 + 启动后台任务
- 后续请求：使用缓存的真实尺寸
- 缓存按 session_id + resource + scene 组织

### 3. 轻量级实现
- 只下载图片头部信息提取尺寸
- 立即丢弃图片数据，不占用内存
- 超时保护（默认 10 秒）

## 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│ 第一次请求（图片 URL）                                        │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ 检查缓存是否有尺寸      │
              └───────────────────────┘
                          │
                          ▼
                    ┌─────────┐
                    │ 未找到   │
                    └─────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌──────────────────────┐      ┌──────────────────────┐
│ 使用占位符尺寸        │      │ 启动后台任务          │
│ (1080x1920)          │      │ - 下载图片            │
│                      │      │ - 提取尺寸            │
│ 立即返回响应          │      │ - 缓存结果            │
└──────────────────────┘      │ - 删除图片数据        │
                              └──────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 第二次请求（相同图片 URL）                                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ 检查缓存是否有尺寸      │
              └───────────────────────┘
                          │
                          ▼
                    ┌─────────┐
                    │ 找到！   │
                    └─────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ 使用缓存的真实尺寸     │
              │ (例如: 1242x2688)     │
              │                       │
              │ 立即返回响应           │
              └───────────────────────┘
```

## 实现细节

### 核心组件

#### 1. ImageDimensionFetcher (`app/services/image_dimension_fetcher.py`)

```python
class ImageDimensionFetcher:
    async def fetch_dimensions(self, url: str) -> Optional[tuple[int, int]]:
        """下载图片并提取尺寸"""
        
    async def fetch_and_cache(
        self, url: str, cache_service, session_id: str, scene: int
    ) -> None:
        """后台任务：获取尺寸并缓存"""
        
    async def get_cached_dimensions(
        self, url: str, cache_service, session_id: str, scene: int
    ) -> Optional[tuple[int, int]]:
        """从缓存获取尺寸"""
```

#### 2. 集成到 predict.py

```python
# 在 get_merge_step_analysis_result 函数中
if image_format == "url":
    # 尝试从缓存获取尺寸
    cached_dimensions = await dimension_fetcher.get_cached_dimensions(...)
    
    if cached_dimensions:
        image_width, image_height = cached_dimensions
    else:
        # 使用占位符
        image_width = 1080
        image_height = 1920
        
        # 启动后台任务
        asyncio.create_task(
            dimension_fetcher.fetch_and_cache(...)
        )
```

### 缓存结构

缓存使用 `SessionCategorizedCacheService`：

```python
{
    "session_id": "test_session",
    "category": "image_dimensions",
    "resource": "https://example.com/screenshot.jpg",
    "scene": 1,
    "payload": {
        "width": 1242,
        "height": 2688,
        "url": "https://example.com/screenshot.jpg"
    }
}
```

## 配置

### 环境变量

```bash
# 使用 URL 模式（启用尺寸缓存）
MULTIMODAL_IMAGE_FORMAT=url

# 或使用 base64 模式（直接获取尺寸，不需要缓存）
MULTIMODAL_IMAGE_FORMAT=base64
```

### 超时设置

默认超时为 10 秒，可以在创建 `ImageDimensionFetcher` 时修改：

```python
fetcher = ImageDimensionFetcher(timeout=15.0)
```

## 日志示例

### 首次请求（未缓存）

```
INFO - Using placeholder dimensions: 1080x1920
INFO - Started background task to fetch dimensions for https://example.com/test.jpg
INFO - Using URL format (skipping download): https://example.com/test.jpg
INFO - Background task: Fetching dimensions for https://example.com/test.jpg
INFO - Fetched dimensions for https://example.com/test.jpg: 1242x2688
INFO - Background task: Cached dimensions for https://example.com/test.jpg: 1242x2688
```

### 后续请求（已缓存）

```
INFO - Using cached dimensions for https://example.com/test.jpg: 1242x2688
INFO - Using cached dimensions: 1242x2688
INFO - Using URL format (skipping download): https://example.com/test.jpg
```

## 优势

### 1. 性能优化
- 首次请求不等待图片下载，响应更快
- 后续请求使用缓存，无需重复下载
- 后台任务不阻塞主流程

### 2. 资源节约
- 只下载一次图片（在后台）
- 立即释放图片数据，不占用内存
- 缓存复用，减少网络请求

### 3. 准确性提升
- 后续请求使用真实尺寸
- 提高坐标归一化的准确性
- 改善气泡检测质量

## 测试

运行测试：

```bash
python -m pytest test_image_dimension_cache.py -v
```

测试覆盖：
- ✅ 成功获取尺寸
- ✅ HTTP 错误处理
- ✅ 缓存写入
- ✅ 缓存读取
- ✅ 缓存未命中
- ✅ 多条缓存记录（使用最新）
- ✅ 全局实例单例

## 注意事项

### 1. 缓存失效
- 如果图片 URL 的内容更新，缓存的尺寸可能过时
- 可以通过更换 session_id 来强制重新获取

### 2. 错误处理
- 后台任务失败不影响主流程
- 失败时记录警告日志
- 下次请求会重试后台任务

### 3. 占位符尺寸
- 1080x1920 是典型的移动设备截图比例
- 对于大多数场景，占位符尺寸足够准确
- 真实尺寸主要用于提高精度

## 相关文件

- `app/services/image_dimension_fetcher.py` - 核心实现
- `app/api/v1/predict.py` - 集成点（第 670-710 行）
- `test_image_dimension_cache.py` - 测试文件
- `app/services/image_fetcher.py` - 原有的图片下载器（base64 模式使用）

## 未来改进

1. **持久化缓存**：使用 Redis 或数据库存储，跨会话复用
2. **预热机制**：批量预下载常用图片的尺寸
3. **智能占位符**：根据历史数据动态调整占位符尺寸
4. **尺寸验证**：检测异常尺寸（过大/过小）并记录
