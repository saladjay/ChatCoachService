# Cache Operations Logging (缓存操作日志)

## 概述

本文档说明如何使用环境变量控制cache相关的详细调试日志，用于调试Redis缓存操作、scene参数处理和缓存键生成等问题。

## 环境变量配置

使用 `DEBUG_LOG_CACHE_OPERATIONS` 环境变量来控制cache相关的详细调试日志。

### 启用cache调试日志

```bash
# Linux/Mac
export DEBUG_LOG_CACHE_OPERATIONS=true

# Windows PowerShell
$env:DEBUG_LOG_CACHE_OPERATIONS="true"

# Windows CMD
set DEBUG_LOG_CACHE_OPERATIONS=true
```

### 禁用cache调试日志（默认）

```bash
# Linux/Mac
export DEBUG_LOG_CACHE_OPERATIONS=false
# 或者不设置该环境变量

# Windows PowerShell
$env:DEBUG_LOG_CACHE_OPERATIONS="false"

# Windows CMD
set DEBUG_LOG_CACHE_OPERATIONS=false
```

## 调试日志内容

当启用时，会打印以下详细信息：

### 1. Cache写入（append_event）
- **原始scene值和类型**：显示传入的scene参数（可能是int或string）
- **转换后的scene字符串**：显示转换为字符串后的值
- **最终的session_id**：显示包含scene的完整session_id（格式：`{conversation_id}_{scene}`）
- **Category和Resource信息**：显示缓存的类别和资源URL
- **Redis key名称**：显示实际使用的Redis键名
- **策略和模型信息**：显示`_strategy`（multimodal/premium/traditional）和`_model`字段

### 2. Cache读取（get_resource_category_last）
- **读取尝试的详细信息**：显示正在读取的category、resource和scene
- **Redis key名称**：显示查询的Redis键名
- **返回的值**：显示Redis返回的原始值（前200字符）
- **解析后的结果**：显示JSON解析后的结果结构
- **缓存命中的策略和模型信息**：显示缓存数据的来源（multimodal/premium/traditional）

### 3. Orchestrator cache操作
- **Scene ID捕获**：在premium后台任务中捕获scene ID的日志
- **Multimodal结果缓存**：显示multimodal模型结果的缓存操作
- **Premium结果缓存**：显示premium模型结果的后台缓存操作
- **Cache读取尝试**：显示每次尝试读取缓存的详细信息
- **Cache命中详情**：显示缓存命中时的策略和模型信息

## 示例日志输出

### Cache写入示例

```
2026-02-10 21:08:32,817 - app.services.session_categorized_cache_service - ERROR - ===== APPEND_EVENT SCENE DEBUG =====
2026-02-10 21:08:32,817 - app.services.session_categorized_cache_service - ERROR - Original scene: '1' (type: int)
2026-02-10 21:08:32,818 - app.services.session_categorized_cache_service - ERROR - Converted scene_str: '1'
2026-02-10 21:08:32,818 - app.services.session_categorized_cache_service - ERROR - Final session_id: '1770728910011_1'
2026-02-10 21:08:32,818 - app.services.session_categorized_cache_service - ERROR - Category: screenshot_parse, Resource: https://test-r2.zhizitech.org/long_sentence.png...
2026-02-10 21:08:32,818 - app.services.session_categorized_cache_service - ERROR - ===== END APPEND_EVENT SCENE DEBUG =====
2026-02-10 21:08:32,821 - app.services.session_categorized_cache_service - ERROR - ===== REDIS SET DEBUG =====
2026-02-10 21:08:32,821 - app.services.session_categorized_cache_service - ERROR - Setting last_key: cache:s:1770728910011_1:r:c78a2cab8025433e:c:screenshot_parse:last
2026-02-10 21:08:32,821 - app.services.session_categorized_cache_service - ERROR - Event strategy: multimodal, model: mistralai/ministral-3b-2512
2026-02-10 21:08:32,821 - app.services.session_categorized_cache_service - ERROR - ===== END REDIS SET DEBUG =====
```

### Cache读取示例

```
2026-02-10 21:08:44,372 - app.services.session_categorized_cache_service - ERROR - ===== GET_RESOURCE_CATEGORY_LAST SCENE DEBUG =====
2026-02-10 21:08:44,372 - app.services.session_categorized_cache_service - ERROR - Original scene: '1' (type: int)
2026-02-10 21:08:44,372 - app.services.session_categorized_cache_service - ERROR - Converted scene_str: '1'
2026-02-10 21:08:44,372 - app.services.session_categorized_cache_service - ERROR - Final session_id: '1770728910011_1'
2026-02-10 21:08:44,372 - app.services.session_categorized_cache_service - ERROR - Category: context_analysis, Resource: https://test-r2.zhizitech.org/long_sentence.png...
2026-02-10 21:08:44,372 - app.services.session_categorized_cache_service - ERROR - ===== END GET_RESOURCE_CATEGORY_LAST SCENE DEBUG =====
2026-02-10 21:08:44,372 - app.services.session_categorized_cache_service - ERROR - ===== REDIS GET DEBUG =====
2026-02-10 21:08:44,372 - app.services.session_categorized_cache_service - ERROR - Getting last_key: cache:s:1770728910011_1:r:c78a2cab8025433e:c:context_analysis:last
2026-02-10 21:08:44,384 - app.services.session_categorized_cache_service - ERROR - Redis returned value: {"ts":1770728912,"resource_key":"c78a2cab8025433e","category":"context_analysis","payload":{"conversation_summary":"The user asks for effective research methods for writing support, and the AI respond...
2026-02-10 21:08:44,385 - app.services.session_categorized_cache_service - ERROR - ===== END REDIS GET DEBUG =====
2026-02-10 21:08:44,420 - app.services.session_categorized_cache_service - ERROR - ===== PARSED RESULT DEBUG =====
2026-02-10 21:08:44,420 - app.services.session_categorized_cache_service - ERROR - Parsed result keys: dict_keys(['ts', 'resource_key', 'category', 'payload'])
2026-02-10 21:08:44,420 - app.services.session_categorized_cache_service - ERROR - Payload _strategy: multimodal, _model: mistralai/ministral-3b-2512
2026-02-10 21:08:44,420 - app.services.session_categorized_cache_service - ERROR - ===== END PARSED RESULT DEBUG =====
```

### Orchestrator cache操作示例

```
2026-02-10 21:08:32,812 - app.services.orchestrator - ERROR - [1770728910011] ===== SCENE CAPTURE DEBUG =====
2026-02-10 21:08:32,812 - app.services.orchestrator - ERROR - [1770728910011] Captured scene_id value: '1' (type: int)
2026-02-10 21:08:32,812 - app.services.orchestrator - ERROR - [1770728910011] ===== END SCENE CAPTURE DEBUG =====

2026-02-10 21:08:32,817 - app.services.orchestrator - ERROR - [1770728910011] ===== MULTIMODAL CACHE WRITE DEBUG =====
2026-02-10 21:08:32,817 - app.services.orchestrator - ERROR - [1770728910011] About to cache multimodal results: resource=None, resources=['https://test-r2.zhizitech.org/long_sentence.png'], scene=1
2026-02-10 21:08:32,817 - app.services.orchestrator - ERROR - [1770728910011] Multimodal strategy=multimodal, model=mistralai/ministral-3b-2512
2026-02-10 21:08:32,817 - app.services.orchestrator - ERROR - [1770728910011] ===== END MULTIMODAL CACHE WRITE DEBUG =====
```

## 使用场景

### 1. 调试Premium缓存问题
当premium模型的结果没有被正确缓存或读取时，启用此日志可以：
- 验证scene ID是否正确传递
- 检查Redis键名是否匹配
- 确认缓存数据的策略标记

### 2. 调试Scene参数处理
当scene参数（int类型）转换为字符串时出现问题，可以：
- 查看原始scene值和类型
- 验证转换后的字符串
- 确认最终的session_id格式

### 3. 调试缓存键冲突
当不同的缓存数据相互覆盖时，可以：
- 检查Redis键名的生成逻辑
- 验证resource_key的计算
- 确认category的使用

## 性能影响

- **禁用时（默认）**：无性能影响，只有INFO级别的简要日志
- **启用时**：会产生大量ERROR级别的详细日志，建议仅在调试时使用
  - 每次cache操作会额外打印5-10行日志
  - 日志量可能增加10-20倍
  - 不建议在生产环境长期启用

## 相关文件

- `app/core/config.py` - 配置定义（`DebugConfig.log_cache_operations`）
- `app/services/session_categorized_cache_service.py` - Cache服务日志实现
- `app/services/orchestrator.py` - Orchestrator cache操作日志实现

## 相关文档

- [Configuration Guide](./CONFIGURATION.md) - 完整的调试配置说明
- [Merge Step Logging](./MERGE_STEP_LOGGING.md) - Merge step相关日志配置
- [Timing Logs](./TIMING_LOGS.md) - 性能计时日志配置

## 更新历史

- 2026-02-10: 初始版本，添加cache操作日志控制功能
