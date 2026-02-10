# 边界框坐标修复总结

**日期**: 2026-02-10  
**状态**: ✅ 已完成

## 问题描述

用户报告标注图片（`test29-31-annotated1.jpg`, `test29-31-annotated2.jpg`）中的矩形框比实际对话气泡小。

## 快速诊断

```python
# 图片尺寸
Image: 574 x 1279 pixels

# 日志中的坐标
[1] talker(left) OK bbox=[0,160,300,250]
[2] user(right) OK bbox=[300,160,600,300]

# 问题：x2=600 > 图片宽度574 ❌
```

## 根本原因

LLM 返回的坐标是归一化的（0-1000 范围），但代码将其视为像素坐标，导致：
- 坐标超出图片边界
- 绘制的矩形框位置和大小错误

## 解决方案

在 `app/services/merge_step_adapter.py` 中添加**两遍处理算法**：

### 第一遍：检测坐标尺度
```python
# 检查所有气泡，确定坐标格式
if all_coords <= 1.0:
    scale = "normalized_0_1"      # 0-1 归一化
elif max_coord > image_size:
    scale = "normalized_0_1000"   # 0-1000 归一化
else:
    scale = "pixels"              # 像素坐标
```

### 第二遍：统一归一化
```python
# 根据检测到的尺度转换所有坐标
if scale == "normalized_0_1":
    x = x * image_width
elif scale == "normalized_0_1000":
    x = (x / 1000.0) * image_width
# else: 保持像素坐标不变
```

## 修复效果

### 修复前
```
bbox=[0,160,300,250]    → 直接使用 → 超出边界 ❌
bbox=[300,160,600,300]  → 直接使用 → 超出边界 ❌
```

### 修复后
```
检测到 0-1000 尺度 → 自动归一化
bbox=[0,160,300,250]    → [0.0, 204.6, 172.2, 319.8]   ✓
bbox=[300,160,600,300]  → [172.2, 204.6, 344.4, 383.7] ✓
```

## 测试结果

创建了 `test_bbox_normalization.py`，测试三种场景：

1. ✅ **0-1000 归一化坐标** - 自动检测并转换
2. ✅ **0-1 归一化坐标** - 自动检测并转换
3. ✅ **像素坐标** - 保持不变

所有测试通过！

## 影响范围

- ✅ 向后兼容 - 支持多种坐标格式
- ✅ 自动检测 - 无需手动配置
- ✅ 清晰日志 - 记录归一化操作
- ✅ 错误验证 - 检测无效坐标

## 相关文件

- `app/services/merge_step_adapter.py` - **已修改**
- `test_bbox_normalization.py` - **新增**
- `docs/fixes/bbox-coordinate-issue.md` - 详细文档
- `docs/fixes/README.md` - 已更新

## 下一步

如果用户重新运行相同的图片：
1. 坐标将自动归一化到正确范围
2. 日志会显示归一化操作
3. 标注图片中的矩形框将正确显示

---

**修复完成** ✅
