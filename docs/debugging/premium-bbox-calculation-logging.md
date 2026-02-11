# Premium 气泡坐标计算详细日志

**功能**: 详细记录 Premium 模型对气泡边界框坐标的计算过程  
**环境变量**: `DEBUG_LOG_PREMIUM_BBOX_CALCULATION`  
**默认值**: `false`（关闭）

## 概述

当启用此调试选项时，系统会详细记录 Premium 模型处理气泡坐标的每一步：

1. **坐标尺度检测** - 判断坐标是像素值还是归一化值
2. **坐标归一化** - 将坐标转换为像素值（如需要）
3. **坐标验证** - 检查坐标是否有效
4. **整数化处理** - 将坐标四舍五入为整数
5. **最终总结** - 汇总所有气泡的处理结果

## 启用方法

### 方法 1: 环境变量

```bash
export DEBUG_LOG_PREMIUM_BBOX_CALCULATION=true
```

### 方法 2: .env 文件

在项目根目录的 `.env` 文件中添加：

```
DEBUG_LOG_PREMIUM_BBOX_CALCULATION=true
```

### 方法 3: Python 代码

```python
import os
os.environ['DEBUG_LOG_PREMIUM_BBOX_CALCULATION'] = 'true'

# 重新加载配置
from app.core.config import settings
settings.debug_config.log_premium_bbox_calculation = True
```

## 日志输出示例

### 完整日志结构

```
================================================================================
PREMIUM BBOX CALCULATION - START
================================================================================
Image dimensions (actual): 716x1279
Total bubbles to process: 8

────────────────────────────────────────────────────────────────────────────────
PASS 1: COORDINATE SCALE DETECTION
────────────────────────────────────────────────────────────────────────────────
  Bubble 1: bbox=[27.0, 193.0, 94.0, 235.0]
  Bubble 2: bbox=[27.0, 243.0, 226.0, 296.0]
  ...

  Detection result: PIXELS (no normalization needed)
  Reason: All coordinates within image bounds
  Max X: 689.0 <= Image Width: 716
  Max Y: 1033.0 <= Image Height: 1279

────────────────────────────────────────────────────────────────────────────────
PASS 2: COORDINATE NORMALIZATION AND VALIDATION
────────────────────────────────────────────────────────────────────────────────
Scale to apply: pixels

  Bubble 1:
    Raw coordinates: [27.0, 193.0, 94.0, 235.0]
    No normalization needed (already in pixels)
    After normalization: [27.00, 193.00, 94.00, 235.00]
    After rounding to integers: [27, 193, 94, 235]
    Final dimensions: 67px × 42px
    ✓ Validation passed

  Bubble 2:
    Raw coordinates: [27.0, 243.0, 226.0, 296.0]
    No normalization needed (already in pixels)
    After normalization: [27.00, 243.00, 226.00, 296.00]
    After rounding to integers: [27, 243, 226, 296]
    Final dimensions: 199px × 53px
    ✓ Validation passed

  ...

────────────────────────────────────────────────────────────────────────────────
SUMMARY
────────────────────────────────────────────────────────────────────────────────
Total bubbles processed: 8
Coordinate scale used: pixels
Image dimensions: 716x1279
Average bubble size: 233.9px × 89.2px

Final bubble coordinates:
  [1] talker(left): bbox=[27,193,94,235] size=67×42px
  [2] talker(left): bbox=[27,243,226,296] size=199×53px
  [3] talker(left): bbox=[27,312,305,365] size=278×53px
  [4] user(left): bbox=[27,381,328,493] size=301×112px
  [5] user(right): bbox=[447,514,689,688] size=242×174px
  [6] user(right): bbox=[447,709,689,883] size=242×174px
  [7] talker(left): bbox=[27,905,313,958] size=286×53px
  [8] talker(left): bbox=[27,980,283,1033] size=256×53px

================================================================================
PREMIUM BBOX CALCULATION - END
================================================================================
```

## 日志内容详解

### PASS 1: 坐标尺度检测

**目的**: 判断 LLM 返回的坐标格式

**检测逻辑**:
1. 检查所有坐标是否 ≤ 1.0 → **0-1 归一化**
2. 检查是否有坐标超出图片边界 → **0-1000 归一化**
3. 否则 → **像素坐标**

**输出信息**:
- 每个气泡的原始坐标
- 检测到的坐标尺度
- 检测原因和依据

### PASS 2: 坐标归一化和验证

**目的**: 将坐标转换为像素值并验证

**处理步骤**:

#### 1. 原始坐标
```
Raw coordinates: [27.0, 193.0, 94.0, 235.0]
```

#### 2. 归一化（如需要）

**0-1 归一化**:
```
Applying 0-1 normalization:
  x1 = 0.1 * 716 = 71.6
  y1 = 0.2 * 1279 = 255.8
  x2 = 0.3 * 716 = 214.8
  y2 = 0.4 * 1279 = 511.6
```

**0-1000 归一化**:
```
Applying 0-1000 normalization:
  x1 = (100 / 1000) * 716 = 71.6
  y1 = (200 / 1000) * 1279 = 255.8
  x2 = (300 / 1000) * 716 = 214.8
  y2 = (400 / 1000) * 1279 = 511.6
```

**像素坐标**:
```
No normalization needed (already in pixels)
```

#### 3. 归一化后的坐标
```
After normalization: [27.00, 193.00, 94.00, 235.00]
```

#### 4. 整数化
```
After rounding to integers: [27, 193, 94, 235]
```

#### 5. 最终尺寸
```
Final dimensions: 67px × 42px
```

#### 6. 验证结果
```
✓ Validation passed
```

或者如果有错误：
```
⚠️  Validation errors: x2=50 > image_width=716, y2=1500 > image_height=1279
```

### SUMMARY: 处理总结

**统计信息**:
- 处理的气泡总数
- 使用的坐标尺度
- 图片尺寸
- 平均气泡大小

**最终坐标列表**:
- 每个气泡的最终坐标
- 气泡尺寸
- 发送者和位置信息

## 使用场景

### 1. 调试坐标问题

当发现气泡位置不正确时，启用此日志可以看到：
- LLM 返回的原始坐标
- 坐标是如何被检测和转换的
- 最终使用的坐标值

### 2. 验证 LLM 输出

检查 LLM 是否按照 prompt 要求返回正确格式的坐标：
- v3.0 prompt 要求像素坐标
- 如果检测到归一化坐标，说明 LLM 没有遵循 prompt

### 3. 性能分析

通过平均气泡大小和坐标分布，可以：
- 分析气泡检测的准确性
- 发现异常的气泡尺寸
- 优化坐标处理逻辑

### 4. 问题排查

当出现以下问题时特别有用：
- 气泡框太小或太大
- 气泡位置偏移
- 坐标超出图片边界
- 坐标验证失败

## 性能影响

**日志开销**: 
- 每个气泡约 10-15 行日志
- 8 个气泡约 120-150 行日志
- 对性能影响极小（主要是 I/O）

**建议**:
- ✅ 开发环境：可以启用
- ✅ 调试问题：临时启用
- ❌ 生产环境：不建议启用（日志量大）

## 相关配置

### 其他调试选项

在 `app/core/config.py` 的 `DebugConfig` 中：

```python
class DebugConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEBUG_")
    
    # 竞速策略调试
    race_wait_all: bool = False
    
    # 详细日志选项
    log_merge_step_extraction: bool = True      # 记录提取的气泡
    log_screenshot_parse: bool = True           # 记录截图解析
    log_race_strategy: bool = True              # 记录竞速策略
    log_llm_calls: bool = False                 # 记录 LLM 调用
    log_validation: bool = False                # 记录验证详情
    log_premium_bbox_calculation: bool = False  # 记录气泡坐标计算 ⭐
```

### 环境变量前缀

所有调试选项都使用 `DEBUG_` 前缀：

```bash
DEBUG_RACE_WAIT_ALL=true
DEBUG_LOG_MERGE_STEP_EXTRACTION=true
DEBUG_LOG_SCREENSHOT_PARSE=true
DEBUG_LOG_RACE_STRATEGY=true
DEBUG_LOG_LLM_CALLS=true
DEBUG_LOG_VALIDATION=true
DEBUG_LOG_PREMIUM_BBOX_CALCULATION=true  # 本功能
```

## 测试

运行测试脚本查看日志输出：

```bash
python test_premium_bbox_logging.py
```

测试脚本会：
1. 启用详细日志
2. 处理 8 个气泡
3. 显示完整的计算过程
4. 输出最终结果

## 相关文件

- `app/core/config.py` - 配置定义
- `app/services/merge_step_adapter.py` - 日志实现
- `test_premium_bbox_logging.py` - 测试脚本
- `docs/debugging/premium-bbox-calculation-logging.md` - 本文档

## 总结

这个调试功能提供了对 Premium 模型气泡坐标计算的完整可见性，帮助：

✅ 理解坐标转换过程  
✅ 发现坐标问题  
✅ 验证 LLM 输出  
✅ 优化坐标处理逻辑  

通过环境变量控制，可以在需要时轻松启用，不影响生产环境性能。
