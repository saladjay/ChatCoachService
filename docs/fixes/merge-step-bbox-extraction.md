# Merge Step Bbox 坐标提取修复

## 问题描述

在使用 merge_step 优化流程时，`DialogItem` 的 `position` 字段被硬编码为 `[0.0, 0.0, 0.0, 0.0]`，导致丢失了气泡的真实坐标信息。

```python
# 之前的代码
dialog_item = DialogItem(
    position=[0.0, 0.0, 0.0, 0.0],  # Position not available from merge_step
    text=msg.content,
    speaker=msg.speaker,
    from_user=(msg.speaker == "user"),
)
```

## 根本原因

1. **数据流断裂**：
   - merge_step 的 LLM 输出包含完整的 bbox 坐标（在 `screenshot_parse.bubbles[].bbox` 中）
   - `orchestrator.merge_step_analysis()` 只返回 `ContextResult` 和 `SceneAnalysisResult`
   - `ContextResult.conversation` 中的 `Message` 对象不包含位置信息
   - `predict.py` 无法访问原始的 bbox 数据

2. **数据结构不匹配**：
   - `Message` 模型只有 `id`, `speaker`, `content`, `timestamp` 字段
   - `DialogItem` 需要 `position` 字段（bbox 坐标）
   - 转换过程中丢失了位置信息

## 解决方案

### 1. 修改 `orchestrator.merge_step_analysis()` 返回值

让方法返回原始的 `parsed_json`，以便访问 bbox 数据：

```python
# app/services/orchestrator.py
async def merge_step_analysis(
    self,
    request: GenerateReplyRequest,
    image_url: str,
    image_base64: str,
    image_width: int,
    image_height: int,
) -> tuple[ContextResult, SceneAnalysisResult, dict]:  # 添加 dict 返回值
    """
    Returns:
        Tuple of (ContextResult, SceneAnalysisResult, parsed_json)
        The parsed_json contains the raw merge_step output including bbox coordinates
    """
    # ... 处理逻辑 ...
    
    return context, scene, parsed_json  # 返回原始 JSON
```

### 2. 在 `predict.py` 中提取 bbox 坐标

从 `parsed_json` 中提取 bbox 并创建 `DialogItem`：

```python
# app/api/v1/predict.py
# Call merge_step_analysis
context, scene, parsed_json = await orchestrator.merge_step_analysis(
    request=orchestrator_request,
    image_url=content_url,
    image_base64=image_base64,
    image_width=image_width,
    image_height=image_height,
)

# Extract bubbles with bbox information from parsed_json
screenshot_data = parsed_json.get("screenshot_parse", {})
bubbles = screenshot_data.get("bubbles", [])

# Convert context.conversation to dialogs with bbox information
dialogs = []
for idx, msg in enumerate(context.conversation):
    # Try to find matching bubble for this message
    bbox = [0.0, 0.0, 0.0, 0.0]  # Default if not found
    
    if idx < len(bubbles):
        bubble = bubbles[idx]
        bbox_data = bubble.get("bbox", {})
        
        # Extract bbox coordinates and normalize to 0-1 range
        x1 = float(bbox_data.get("x1", 0))
        y1 = float(bbox_data.get("y1", 0))
        x2 = float(bbox_data.get("x2", 0))
        y2 = float(bbox_data.get("y2", 0))
        
        # Normalize coordinates if they are in pixel format
        # (merge_step v3.0 returns pixel coordinates)
        if x1 > 1.0 or y1 > 1.0 or x2 > 1.0 or y2 > 1.0:
            # Coordinates are in pixels, normalize to 0-1
            x1_norm = x1 / image_width if image_width > 0 else 0.0
            y1_norm = y1 / image_height if image_height > 0 else 0.0
            x2_norm = x2 / image_width if image_width > 0 else 0.0
            y2_norm = y2 / image_height if image_height > 0 else 0.0
            bbox = [x1_norm, y1_norm, x2_norm, y2_norm]
        else:
            # Already normalized
            bbox = [x1, y1, x2, y2]
    
    dialog_item = DialogItem(
        position=bbox,
        text=msg.content,
        speaker=msg.speaker,
        from_user=(msg.speaker == "user"),
    )
    dialogs.append(dialog_item)
```

## 关键特性

### 1. 自动坐标归一化

代码自动检测坐标格式并归一化到 0-1 范围：

- **像素坐标**（merge_step v3.0 默认）：如果任何坐标 > 1.0，则除以图片尺寸
- **已归一化坐标**：如果所有坐标 <= 1.0，则直接使用

### 2. 零除保护

防止图片尺寸为 0 导致的除零错误：

```python
x1_norm = x1 / image_width if image_width > 0 else 0.0
```

### 3. 缺失数据处理

如果 bubble 或 bbox 缺失，使用默认值 `[0.0, 0.0, 0.0, 0.0]`：

```python
bbox = [0.0, 0.0, 0.0, 0.0]  # Default if not found

if idx < len(bubbles):
    bubble = bubbles[idx]
    bbox_data = bubble.get("bbox", {})
    # ... 提取坐标 ...
```

### 4. 索引匹配

通过索引匹配 `context.conversation` 中的消息和 `bubbles` 中的气泡：

```python
for idx, msg in enumerate(context.conversation):
    if idx < len(bubbles):
        bubble = bubbles[idx]
        # ... 使用 bubble 的 bbox ...
```

## 数据流

```
┌─────────────────────────────────────────────────────────────┐
│ LLM (merge_step)                                            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ parsed_json           │
              │ {                     │
              │   "screenshot_parse": │
              │     "bubbles": [      │
              │       {               │
              │         "sender": ... │
              │         "text": ...   │
              │         "bbox": {     │
              │           "x1": 100   │
              │           "y1": 200   │
              │           "x2": 300   │
              │           "y2": 400   │
              │         }             │
              │       }               │
              │     ]                 │
              │ }                     │
              └───────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌──────────────────────┐      ┌──────────────────────┐
│ MergeStepAdapter     │      │ orchestrator         │
│ to_context_result()  │      │ merge_step_analysis()│
└──────────────────────┘      └──────────────────────┘
          │                               │
          ▼                               ▼
┌──────────────────────┐      ┌──────────────────────┐
│ ContextResult        │      │ Return:              │
│ - conversation       │      │ (context, scene,     │
│   (Message list)     │      │  parsed_json) ✅     │
│ - emotion_state      │      └──────────────────────┘
│ - intimacy_level     │                  │
└──────────────────────┘                  │
                                          ▼
                              ┌──────────────────────┐
                              │ predict.py           │
                              │ - Extract bubbles    │
                              │ - Match by index     │
                              │ - Normalize bbox     │
                              │ - Create DialogItem  │
                              └──────────────────────┘
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │ DialogItem           │
                              │ - position: [x1, y1, │
                              │             x2, y2]  │
                              │ - text               │
                              │ - speaker            │
                              │ - from_user          │
                              └──────────────────────┘
```

## 测试

运行测试验证功能：

```bash
python -m pytest test_merge_step_bbox_extraction.py -v
```

测试覆盖：
- ✅ 像素坐标归一化
- ✅ 已归一化坐标处理
- ✅ DialogItem 创建
- ✅ 多个气泡提取
- ✅ 缺失 bbox 的后备处理
- ✅ 零除保护

## 影响范围

### 修改的文件

1. **app/services/orchestrator.py**
   - 修改 `merge_step_analysis()` 返回值类型
   - 添加 `parsed_json` 到返回元组
   - 更新文档字符串

2. **app/api/v1/predict.py**
   - 修改 `get_merge_step_analysis_result()` 函数
   - 从 `parsed_json` 提取 bbox 信息
   - 创建带有真实坐标的 `DialogItem`

### 向后兼容性

- ✅ 不影响传统流程（非 merge_step）
- ✅ 缓存的数据结构不变
- ✅ API 响应格式不变
- ⚠️ 调用 `merge_step_analysis()` 的代码需要更新以接收第三个返回值

## 优势

### 1. 完整的坐标信息
- `DialogItem.position` 现在包含真实的气泡坐标
- 客户端可以准确定位每条消息的位置
- 支持气泡高亮、标注等功能

### 2. 与传统流程一致
- merge_step 流程现在返回与传统流程相同的坐标信息
- 统一的数据格式，简化客户端处理

### 3. 自动坐标处理
- 自动检测和归一化坐标格式
- 兼容 v2.0（0-1000 范围）和 v3.0（像素）
- 防御性编程，处理各种边界情况

## 相关文档

- [Merge Step v3.0 兼容性](./merge-step-v3-compatibility.md) - v3.0 prompt 的坐标要求
- [Bbox 坐标归一化](./bbox-coordinate-issue.md) - 坐标归一化的详细说明
- [Premium Bbox 计算日志](../debugging/premium-bbox-calculation-logging.md) - 调试坐标计算

## 相关文件

- `app/services/orchestrator.py` - merge_step_analysis 方法
- `app/api/v1/predict.py` - get_merge_step_analysis_result 函数
- `app/services/merge_step_adapter.py` - MergeStepAdapter 类
- `test_merge_step_bbox_extraction.py` - 测试文件
