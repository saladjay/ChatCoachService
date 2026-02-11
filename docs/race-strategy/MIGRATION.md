# Premium Priority Race Strategy Changes

## 日期: 2026-02-09

## 变更概述

修改了 LLM 竞速策略，现在始终优先使用 premium 模型（Google Gemini 2.0 Flash）的结果，并确保 premium 结果被缓存以供后续使用。

## 新的竞速逻辑

### 1. 始终等待两个模型完成
- 不再使用 `DEBUG_RACE_WAIT_ALL` 配置
- 总是等待 multimodal 和 premium 两个模型都完成
- 这确保我们总能获得 premium 结果（如果成功）

### 2. Premium 优先策略

**决策逻辑：**

1. **如果 premium 有效** → 使用 premium 结果
   - Premium 结果被缓存
   - 当前响应使用 premium 结果

2. **如果 premium 失败/无效，但 multimodal 有效** → 使用 multimodal 结果
   - Multimodal 结果用于当前响应
   - Premium 结果（即使无效）也会尝试缓存（如果可解析）
   - 下次调用时，如果 premium 结果在缓存中，会优先使用

3. **如果两者都失败/无效** → 报错
   - 抛出 `ValueError: Both calls failed or returned invalid data`
   - 不会生成回复

### 3. 缓存策略

**Premium 结果缓存：**
- 如果 premium 结果有效，总是缓存
- 即使当前使用的是 multimodal 结果，premium 结果也会被缓存
- 下次调用相同资源时（`force_regenerate=False`），会使用缓存的 premium 结果

**缓存键：**
- 使用相同的资源键（image URL）
- `context_analysis` 和 `scene_analysis` 分别缓存

## 代码变更

### 1. `app/services/screenshot_parser.py`

**方法签名变更：**
```python
# 之前
async def _race_multimodal_calls(...) -> tuple[str, Any]:
    return (winning_strategy, llm_result)

# 现在
async def _race_multimodal_calls(...) -> tuple[str, Any, Any]:
    return (winning_strategy, winning_result, premium_result_or_none)
```

**返回值：**
- `winning_strategy`: "premium" 或 "multimodal"
- `winning_result`: 用于当前响应的结果
- `premium_result_or_none`: Premium 结果（用于缓存），如果失败则为 None

**新逻辑：**
```python
# 总是等待两个模型
multimodal_strategy, multimodal_result = await multimodal_task
premium_strategy, premium_result = await premium_task

# 验证两个结果
multimodal_valid = validate(multimodal_result)
premium_valid = validate(premium_result)

# 决策
if premium_valid:
    return ("premium", premium_result, premium_result)
elif multimodal_valid:
    return ("multimodal", multimodal_result, premium_result)
else:
    raise ValueError("Both calls failed")
```

### 2. `app/services/orchestrator.py`

**调用变更：**
```python
# 之前
winning_strategy, llm_result = await temp_parser._race_multimodal_calls(...)

# 现在
winning_strategy, llm_result, premium_result = await temp_parser._race_multimodal_calls(...)
```

**Premium 缓存逻辑：**
```python
# 如果 premium 结果可用且与 winning 结果不同
if premium_result and premium_result != llm_result:
    try:
        premium_parsed = parse_json_with_markdown(premium_result.text)
        if validate_merge_step_result(premium_parsed):
            # 解析并缓存 premium 结果
            premium_context, premium_scene = merge_adapter.to_results(premium_parsed)
            await self._cache_payload(request, "context_analysis", premium_context.model_dump())
            await self._cache_payload(request, "scene_analysis", premium_scene.model_dump())
            logger.info("Premium result cached successfully")
    except Exception as e:
        logger.warning(f"Failed to cache premium result: {e}")
```

## 使用场景

### 场景 1: Premium 先完成且有效
```
1. Multimodal 和 Premium 同时开始
2. Premium 先完成，结果有效
3. 使用 Premium 结果生成回复
4. Premium 结果被缓存
5. Multimodal 完成（结果被忽略）
```

### 场景 2: Multimodal 先完成，Premium 后完成且有效
```
1. Multimodal 和 Premium 同时开始
2. Multimodal 先完成，结果有效
3. 等待 Premium 完成
4. Premium 完成，结果有效
5. 使用 Premium 结果生成回复（优先）
6. Premium 结果被缓存
```

### 场景 3: Premium 失败，Multimodal 成功
```
1. Multimodal 和 Premium 同时开始
2. Premium 失败或返回无效结果
3. Multimodal 成功，结果有效
4. 使用 Multimodal 结果生成回复
5. Multimodal 结果被缓存
6. Premium 结果（如果可解析）也尝试缓存
```

### 场景 4: 两者都失败
```
1. Multimodal 和 Premium 同时开始
2. 两者都失败或返回无效结果
3. 抛出错误：ValueError("Both calls failed")
4. 不生成回复
5. 返回错误给用户
```

## 日志输出

**新的日志格式：**
```
INFO - [session] Starting merge_step race: multimodal vs premium (premium priority)
INFO - [session] merge_step multimodal completed in 5000ms (model: ministral-3b)
INFO - [session] merge_step premium completed in 7000ms (model: gemini-2.0-flash)
INFO - [session] merge_step: multimodal result is valid
INFO - [session] merge_step: premium result is valid
INFO - [session] merge_step: Using premium result (preferred)
INFO - [session] Caching premium result for future use
INFO - [session] Premium result cached successfully
```

## 性能影响

### 优点
1. **质量优先**：总是优先使用更高质量的 premium 模型
2. **缓存优化**：Premium 结果被缓存，后续调用更快
3. **容错性**：如果 premium 失败，仍可使用 multimodal 结果

### 缺点
1. **响应时间**：总是等待两个模型，响应时间取决于较慢的模型
2. **成本**：总是调用两个模型，API 成本翻倍

### 成本估算
- Multimodal (ministral-3b): ~$0.0001 per request
- Premium (gemini-2.0-flash): ~$0.0005 per request
- **总成本**: ~$0.0006 per request（之前可能只用一个模型）

## 配置

**移除的配置：**
- `DEBUG_RACE_WAIT_ALL` - 不再使用，总是等待所有模型

**保留的配置：**
- `DEBUG_LOG_MERGE_STEP_EXTRACTION` - 控制日志输出
- `DEBUG_LOG_RACE_STRATEGY` - 控制竞速详情日志

## 测试

```bash
# 测试 premium 优先策略
python tests/load_test.py --url http://localhost:80 --image-url https://test-r2.zhizitech.org/test35.jpg --requests 1 --concurrent 1 --disable-cache --language zh

# 查看日志，确认：
# 1. 两个模型都被调用
# 2. Premium 结果被优先使用
# 3. Premium 结果被缓存
```

## 注意事项

1. **总是等待两个模型**：即使 multimodal 先完成，也会等待 premium
2. **Premium 优先**：只要 premium 有效，就使用 premium
3. **缓存策略**：Premium 结果总是被缓存（如果有效）
4. **错误处理**：两者都失败时，不会生成回复，直接报错
5. **成本考虑**：每次请求都会调用两个模型，成本增加

## 回滚方案

如果需要回滚到之前的"先到先得"策略：

1. 恢复 `_race_multimodal_calls` 方法的返回值为两个元素
2. 恢复 orchestrator 中的调用代码
3. 重新启用 `DEBUG_RACE_WAIT_ALL` 配置

## 相关文件

- `app/services/screenshot_parser.py` - 竞速逻辑实现
- `app/services/orchestrator.py` - 调用和缓存逻辑
- `app/services/merge_step_adapter.py` - 结果验证和转换
- `docs/DEBUG_CONFIGURATION.md` - 调试配置文档
