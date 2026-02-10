# 调试功能文档

本目录包含各种调试功能的使用说明。

## 可用的调试功能

### [Premium 气泡坐标计算详细日志](./premium-bbox-calculation-logging.md)

**环境变量**: `DEBUG_LOG_PREMIUM_BBOX_CALCULATION`

详细记录 Premium 模型处理气泡边界框坐标的完整过程，包括：
- 坐标尺度检测（像素 vs 归一化）
- 坐标转换计算
- 验证和整数化
- 最终结果总结

**使用场景**:
- 调试气泡位置不正确的问题
- 验证 LLM 是否按 prompt 要求返回坐标
- 分析坐标转换逻辑
- 排查坐标超出边界的问题

**启用方法**:
```bash
export DEBUG_LOG_PREMIUM_BBOX_CALCULATION=true
```

或在 `.env` 文件中：
```
DEBUG_LOG_PREMIUM_BBOX_CALCULATION=true
```

## 其他调试选项

所有调试选项都在 `app/core/config.py` 的 `DebugConfig` 类中定义，使用 `DEBUG_` 前缀：

### 竞速策略调试

```bash
# 等待所有模型完成（用于对比）
DEBUG_RACE_WAIT_ALL=true
```

### 组件日志

```bash
# 记录 merge_step 提取的气泡
DEBUG_LOG_MERGE_STEP_EXTRACTION=true

# 记录截图解析的对话
DEBUG_LOG_SCREENSHOT_PARSE=true

# 记录竞速策略详情
DEBUG_LOG_RACE_STRATEGY=true

# 记录详细的 LLM 调用信息
DEBUG_LOG_LLM_CALLS=true

# 记录验证详情
DEBUG_LOG_VALIDATION=true

# 记录 Premium 气泡坐标计算（本功能）
DEBUG_LOG_PREMIUM_BBOX_CALCULATION=true
```

## 性能考虑

| 调试选项 | 日志量 | 性能影响 | 生产环境 |
|---------|--------|---------|---------|
| `RACE_WAIT_ALL` | 中 | 高（等待所有模型） | ❌ 不推荐 |
| `LOG_MERGE_STEP_EXTRACTION` | 低 | 极小 | ✅ 可以 |
| `LOG_SCREENSHOT_PARSE` | 低 | 极小 | ✅ 可以 |
| `LOG_RACE_STRATEGY` | 中 | 极小 | ✅ 可以 |
| `LOG_LLM_CALLS` | 高 | 小 | ⚠️ 谨慎 |
| `LOG_VALIDATION` | 中 | 极小 | ⚠️ 谨慎 |
| `LOG_PREMIUM_BBOX_CALCULATION` | 很高 | 小 | ❌ 不推荐 |

## 最佳实践

### 开发环境

可以启用所有调试选项以获得最大可见性：

```bash
DEBUG_RACE_WAIT_ALL=false  # 除非需要对比
DEBUG_LOG_MERGE_STEP_EXTRACTION=true
DEBUG_LOG_SCREENSHOT_PARSE=true
DEBUG_LOG_RACE_STRATEGY=true
DEBUG_LOG_LLM_CALLS=true
DEBUG_LOG_VALIDATION=true
DEBUG_LOG_PREMIUM_BBOX_CALCULATION=true
```

### 生产环境

只启用必要的日志：

```bash
DEBUG_RACE_WAIT_ALL=false
DEBUG_LOG_MERGE_STEP_EXTRACTION=true
DEBUG_LOG_SCREENSHOT_PARSE=true
DEBUG_LOG_RACE_STRATEGY=true
DEBUG_LOG_LLM_CALLS=false
DEBUG_LOG_VALIDATION=false
DEBUG_LOG_PREMIUM_BBOX_CALCULATION=false
```

### 问题排查

根据问题类型启用相应的调试选项：

**坐标问题**:
```bash
DEBUG_LOG_PREMIUM_BBOX_CALCULATION=true
```

**LLM 调用问题**:
```bash
DEBUG_LOG_LLM_CALLS=true
TRACE_ENABLED=true
TRACE_LOG_LLM_PROMPT=true
```

**竞速策略问题**:
```bash
DEBUG_RACE_WAIT_ALL=true
DEBUG_LOG_RACE_STRATEGY=true
```

**验证问题**:
```bash
DEBUG_LOG_VALIDATION=true
```

## 相关文档

- [Premium 气泡坐标计算日志](./premium-bbox-calculation-logging.md)
- [配置文件说明](../../.env.example)
- [代码配置](../../app/core/config.py)

## 测试脚本

- `test_premium_bbox_logging.py` - 测试 Premium 坐标计算日志

## 添加新的调试功能

如果需要添加新的调试选项：

1. 在 `app/core/config.py` 的 `DebugConfig` 类中添加字段
2. 在代码中检查配置并添加日志
3. 更新 `.env.example` 文件
4. 创建文档说明使用方法
5. 编写测试脚本

示例：

```python
# 1. 在 app/core/config.py 中
class DebugConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEBUG_")
    
    log_my_new_feature: bool = False  # 新功能日志

# 2. 在代码中使用
from app.core.config import settings

if settings.debug_config.log_my_new_feature:
    logger.info("Detailed information about my feature")

# 3. 在 .env.example 中添加
DEBUG_LOG_MY_NEW_FEATURE=false

# 4. 创建文档
docs/debugging/my-new-feature-logging.md

# 5. 编写测试
test_my_new_feature_logging.py
```

## 总结

调试功能通过环境变量控制，可以在需要时轻松启用，不影响生产环境性能。合理使用调试选项可以大大提高问题排查效率。
