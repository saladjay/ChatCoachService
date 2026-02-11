# Merge Step v3.0 Prompt 兼容性

**日期**: 2026-02-10  
**状态**: ✅ 完全兼容

## 概述

检查并更新代码以支持新的 `merge_step_v3.0-compact.txt` prompt，同时保持与 v2.0 的向后兼容性。

## v3.0 Prompt 的主要变化

### 1. 新增 `image_metadata` 字段

```json
{
  "image_metadata": {
    "original_width": 574,
    "original_height": 1279,
    "scaling_confirmed": true
  },
  "screenshot_parse": { ... },
  "conversation_analysis": { ... },
  "scenario_decision": { ... }
}
```

**用途**：
- LLM 报告检测到的原始图片尺寸
- 用于验证坐标是否正确缩放回原始分辨率
- 帮助检测坐标尺度问题

### 2. 强化坐标要求

**v2.0**:
```
bbox:{x1,y1,x2,y2} (original pixels)
```

**v3.0**:
```
bbox:{x1,y1,x2,y2} (Must be absolute original pixels. 
If internal processing uses scaling, you MUST re-scale 
coordinates back to the original Width/Height.)
```

**新增规则**:
- 坐标必须是整数
- 必须满足 x2 > x1 和 y2 > y1
- 坐标必须对齐原始图片的高分辨率像素网格
- **不能使用归一化的 0-1000 尺度**

### 3. 修复 JSON 语法错误

**v2.0** (有语法错误):
```json
"relationship_state":"ignition|propulsion|ventilation|equilibrium,
```

**v3.0** (已修复):
```json
"relationship_state":"ignition|propulsion|ventilation|equilibrium",
```

## 代码更新

### 1. 验证逻辑增强

在 `MergeStepAdapter.validate_merge_output()` 中添加：

```python
# Check for v3.0 image_metadata (optional for backward compatibility)
if "image_metadata" in merge_output:
    metadata = merge_output["image_metadata"]
    logger.info(f"Detected v3.0 format with image_metadata: {metadata}")
    
    # Validate image_metadata structure
    if "original_width" in metadata and "original_height" in metadata:
        width = metadata.get("original_width", 0)
        height = metadata.get("original_height", 0)
        if width > 0 and height > 0:
            logger.info(f"Image dimensions from LLM: {width}x{height}")
        else:
            logger.warning(f"Invalid image dimensions in metadata: {width}x{height}")
else:
    logger.info("No image_metadata found, assuming v2.0 format")
```

**特点**：
- ✅ v3.0 格式：读取并验证 image_metadata
- ✅ v2.0 格式：优雅降级，不报错
- ✅ 向后兼容

### 2. 坐标归一化改进

在 `MergeStepAdapter.to_parsed_screenshot_data()` 中：

#### 2.1 验证 LLM 报告的尺寸

```python
# Check if v3.0 image_metadata is available
image_metadata = merge_output.get("image_metadata", {})
llm_reported_width = image_metadata.get("original_width", 0)
llm_reported_height = image_metadata.get("original_height", 0)

# Validate LLM-reported dimensions against actual dimensions
if llm_reported_width > 0 and llm_reported_height > 0:
    if abs(llm_reported_width - image_width) > 5 or abs(llm_reported_height - image_height) > 5:
        logger.warning(
            f"Image dimension mismatch: LLM reported {llm_reported_width}x{llm_reported_height}, "
            f"actual {image_width}x{image_height}"
        )
```

#### 2.2 改进的警告信息

```python
if coordinate_scale == "normalized_0_1":
    logger.warning(
        f"Detected normalized coordinates (0-1 range) despite v3.0 prompt requiring pixels. "
        f"This may indicate LLM is not following the prompt correctly."
    )
elif coordinate_scale == "normalized_0_1000":
    logger.warning(
        f"Detected coordinates exceeding image bounds. "
        f"Assuming 0-1000 scale. This should not happen with v3.0 prompt."
    )
else:
    logger.debug(f"Coordinates appear to be in pixels (as expected with v3.0 prompt)")
```

#### 2.3 坐标整数化

```python
# Convert to integers as required by v3.0 prompt
x1 = int(round(x1))
y1 = int(round(y1))
x2 = int(round(x2))
y2 = int(round(y2))
```

**注意**：虽然 `BoundingBox` 模型使用 `float` 类型（为了支持归一化坐标），但我们确保传入的值是整数。

### 3. 增强的坐标验证

```python
# Validate final coordinates (v3.0 requirements)
if x1 >= x2 or y1 >= y2:
    logger.error(
        f"Bubble {idx}: Invalid bbox coordinates (violates x2>x1, y2>y1): "
        f"x1={x1:.1f} >= x2={x2:.1f} or y1={y1:.1f} >= y2={y2:.1f}"
    )
```

## 测试覆盖

更新了 `test_bbox_normalization.py` 包含三个测试场景：

### Test Case 1: v2.0 格式（0-1000 归一化）
```python
# 没有 image_metadata
merge_output = {
    "screenshot_parse": { ... },
    "conversation_analysis": { ... },
    "scenario_decision": { ... }
}
```
✅ 自动检测并归一化

### Test Case 2: v3.0 格式（像素坐标）
```python
# 包含 image_metadata
merge_output = {
    "image_metadata": {
        "original_width": 574,
        "original_height": 1279,
        "scaling_confirmed": True
    },
    "screenshot_parse": { ... },
    ...
}
```
✅ 验证尺寸，坐标保持不变

### Test Case 3: 向后兼容（0-1 归一化）
```python
# 旧格式的归一化坐标
"bbox": {"x1": 0.0, "y1": 0.16, "x2": 0.3, "y2": 0.25}
```
✅ 自动检测并转换为像素

## 兼容性矩阵

| Prompt 版本 | image_metadata | 坐标格式 | 代码行为 | 状态 |
|------------|----------------|---------|---------|------|
| v2.0 | ❌ 无 | 像素 | 直接使用 | ✅ |
| v2.0 | ❌ 无 | 0-1000 | 自动归一化 | ✅ |
| v2.0 | ❌ 无 | 0-1 | 自动归一化 | ✅ |
| v3.0 | ✅ 有 | 像素 | 验证尺寸，直接使用 | ✅ |
| v3.0 | ✅ 有 | 0-1000 | 警告 + 归一化 | ✅ |
| v3.0 | ✅ 有 | 0-1 | 警告 + 归一化 | ✅ |

## 预期行为

### 使用 v3.0 Prompt 时

**理想情况**（LLM 正确遵循 prompt）：
```
✓ 坐标是像素值
✓ image_metadata 正确
✓ 无需归一化
✓ 日志：Coordinates appear to be in pixels (as expected with v3.0 prompt)
```

**LLM 未遵循 prompt**（仍返回归一化坐标）：
```
⚠️ 坐标超出边界或在 0-1 范围
⚠️ 自动检测并归一化
⚠️ 日志：WARNING - This should not happen with v3.0 prompt
✓ 功能正常，但需要检查 LLM 配置
```

### 使用 v2.0 Prompt 时

```
✓ 无 image_metadata（正常）
✓ 自动检测坐标尺度
✓ 必要时归一化
✓ 完全向后兼容
```

## 优势

1. **完全向后兼容** - v2.0 和 v3.0 prompt 都能正常工作
2. **自动检测** - 无需手动配置坐标格式
3. **智能警告** - 当 LLM 不遵循 v3.0 要求时发出警告
4. **尺寸验证** - 利用 v3.0 的 image_metadata 验证坐标正确性
5. **健壮性** - 即使 LLM 返回错误格式也能自动修正

## 相关文件

- `prompts/versions/merge_step_v2.0-compact.txt` - 旧版本 prompt
- `prompts/versions/merge_step_v3.0-compact.txt` - 新版本 prompt
- `app/services/merge_step_adapter.py` - **已更新** - 支持 v3.0
- `test_bbox_normalization.py` - **已更新** - 测试 v3.0 兼容性
- `docs/fixes/bbox-coordinate-issue.md` - 坐标问题详细分析

## 结论

✅ **代码完全兼容 merge_step v3.0 prompt**

- 支持新的 `image_metadata` 字段
- 验证 LLM 报告的图片尺寸
- 强化坐标验证（x2>x1, y2>y1）
- 坐标整数化
- 保持向后兼容性
- 所有测试通过

可以安全地切换到 v3.0 prompt，代码会自动适配。
