# Coordinate Normalization Fix

## 问题描述

在调用 predict 端点时出现验证错误：

```
ValidationError: 1 validation error for DialogItem
position
  Value error, position[0] (min_x) must be in range [0.0, 1.0], got 67.0
```

## 根本原因

`analyze_chat_image` 函数返回的坐标是**像素坐标**（例如：`[67.0, 304.0, 224.0, 323.0]`），而 `DialogItem` 模型要求坐标必须是**归一化坐标**（0.0-1.0 范围）。

### 代码位置

在 `core/screenshotanalysis/src/screenshotanalysis/dialog_pipeline2.py` 第 203 行：

```python
dialog = {
    "speaker": speaker,
    "text": text_value,
    "box": [int(v) for v in box.box.tolist()],  # 像素坐标
}
```

## 解决方案

在 `app/api/v1/predict.py` 中添加坐标归一化逻辑：

### 修改内容

1. **加载图像获取尺寸**
   ```python
   from PIL import Image
   import httpx
   from io import BytesIO
   
   if content_url.startswith(('http://', 'https://')):
       # 从 URL 下载图像
       async with httpx.AsyncClient() as client:
           response = await client.get(content_url, timeout=30.0)
           response.raise_for_status()
           image = Image.open(BytesIO(response.content))
   else:
       # 从本地路径加载
       image = Image.open(content_url)
   
   image_width, image_height = image.size
   ```

2. **归一化坐标**
   ```python
   # 像素坐标
   box = dialog_data.get("box", [0, 0, 0, 0])
   
   # 归一化到 [0.0, 1.0] 范围
   normalized_box = [
       float(box[0]) / image_width,   # min_x
       float(box[1]) / image_height,  # min_y
       float(box[2]) / image_width,   # max_x
       float(box[3]) / image_height,  # max_y
   ]
   ```

3. **使用归一化坐标创建 DialogItem**
   ```python
   dialog_item = DialogItem(
       position=normalized_box,  # 使用归一化坐标
       text=dialog_data.get("text", ""),
       speaker=speaker,
       from_user=from_user,
   )
   ```

## 示例

### 输入（像素坐标）
```json
{
  "box": [67, 304, 224, 323]
}
```

### 图像尺寸
- 宽度: 1080 像素
- 高度: 1920 像素

### 输出（归一化坐标）
```json
{
  "position": [
    0.062,  // 67 / 1080
    0.158,  // 304 / 1920
    0.207,  // 224 / 1080
    0.168   // 323 / 1920
  ]
}
```

## 错误处理

如果无法获取图像尺寸（例如网络错误），代码会：
1. 记录错误日志
2. 使用 fallback 值 (1.0, 1.0)
3. 继续处理（假设坐标已经归一化）

```python
except Exception as e:
    logger.error(f"Failed to get image dimensions: {e}")
    # Fallback: assume coordinates are already normalized
    image_width, image_height = 1.0, 1.0
```

## 验证

修复后，坐标验证应该通过：

```python
# 验证规则（在 DialogItem 模型中）
for i, coord in enumerate(position):
    if not (0.0 <= coord <= 1.0):
        raise ValueError(
            f"position[{i}] must be in range [0.0, 1.0], got {coord}"
        )
```

## 相关文件

- `app/api/v1/predict.py` - 添加了坐标归一化逻辑
- `app/models/v1_api.py` - DialogItem 模型定义和验证
- `core/screenshotanalysis/src/screenshotanalysis/dialog_pipeline2.py` - 返回像素坐标的源头

## 注意事项

1. **性能影响**: 每个图像都需要额外加载一次来获取尺寸，但这是必要的
2. **网络请求**: 对于 URL 图像，会发起两次请求（一次获取尺寸，一次在 analyze_chat_image 中）
3. **未来优化**: 可以考虑让 `analyze_chat_image` 直接返回图像尺寸和归一化坐标

## 测试

可以使用以下测试用例验证修复：

```python
# 测试像素坐标转换
image_width = 1080
image_height = 1920
pixel_box = [67, 304, 224, 323]

normalized_box = [
    float(pixel_box[0]) / image_width,
    float(pixel_box[1]) / image_height,
    float(pixel_box[2]) / image_width,
    float(pixel_box[3]) / image_height,
]

# 验证范围
assert all(0.0 <= coord <= 1.0 for coord in normalized_box)
print(f"Normalized: {normalized_box}")
# 输出: Normalized: [0.062, 0.158, 0.207, 0.168]
```
