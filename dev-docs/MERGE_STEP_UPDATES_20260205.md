# Merge Step 更新日志 - 2026-02-05

## 更新内容

### 1. 添加 --log-prompt 支持到 merge_step ✅

**问题**: merge_step 流程没有记录 prompt 和 response，导致 `--log-prompt` 参数对 merge_step 不生效。

**解决方案**: 在 `app/services/orchestrator.py` 的 `merge_step_analysis()` 函数中添加 prompt logging。

**修改文件**: `app/services/orchestrator.py`

**效果**:
- 当设置 `TRACE_LOG_LLM_PROMPT=true` 时，merge_step 会记录完整的 prompt 和 response
- 与传统流程保持一致的 logging 行为
- 支持 `--log-prompt` 启动参数

### 2. 删除未使用的函数 ✅

**问题**: `app/api/v1/predict.py` 中存在未使用的 `handle_image_old()` 函数，占用代码空间。

**解决方案**: 删除 `handle_image_old()` 函数（约 300 行代码）。

**修改文件**: `app/api/v1/predict.py`

**效果**:
- 减少代码冗余
- 提高代码可维护性
- 减少文件大小

### 3. Load Test 打印配置信息 ✅

**问题**: 
1. 运行 load test 时无法看到当前的 provider 和模型配置
2. `app/core/config.py` 中的 LLM 配置是硬编码的 fallback 值
3. 实际使用的配置在 `core/llm_adapter/config.yaml`，容易混淆

**解决方案**: 
1. 在 `tests/load_test.py` 中添加配置信息打印
2. 同时显示 fallback 配置和实际使用的配置
3. 在 `app/core/config.py` 中添加注释说明
4. 创建 `dev-docs/LLM_CONFIG_CLARIFICATION.md` 文档

**修改文件**: 
- `tests/load_test.py`
- `app/core/config.py`
- `dev-docs/LLM_CONFIG_CLARIFICATION.md` (新建)

**效果**:
- 运行 load test 时显示实际使用的配置
- 清楚区分 fallback 配置和实际配置
- 便于验证配置是否正确

## 配置说明

### 重要发现：配置重复问题

系统中存在两个 LLM 配置位置：

1. **`app/core/config.py`** - Fallback 配置（不是实际使用的）
   ```python
   class LLMConfig(BaseSettings):
       default_provider: str = "openrouter"
       default_model: str = "google/gemini-2.0-flash-lite-001"
   ```

2. **`core/llm_adapter/config.yaml`** - 实际使用的配置
   ```yaml
   llm:
     default_provider: openrouter
   providers:
     openrouter:
       models:
         cheap: google/gemini-2.0-flash-lite-001
         normal: google/gemini-2.0-flash-lite-001
         premium: google/gemini-2.0-flash-lite-001
         multimodal: qwen/qwen3-vl-30b-a3b-instruct
   ```

### 配置优先级

```
core/llm_adapter/config.yaml (实际使用) ← 修改此文件
    ↓
环境变量 (${OPENROUTER_API_KEY})
    ↓
app/core/config.py (fallback，仅用于显示)
```

### 如何修改配置

✅ **推荐**: 修改 `core/llm_adapter/config.yaml`

```bash
vim core/llm_adapter/config.yaml
```

✅ **推荐**: 使用环境变量

```bash
export OPENROUTER_API_KEY=sk-or-v1-xxx
export MULTIMODAL_DEFAULT_PROVIDER=gemini
```

❌ **不推荐**: 修改 `app/core/config.py`（这只是 fallback 值）

## 使用示例

### 查看配置

```bash
# 运行 load test 查看配置
python tests/load_test.py --help

# 输出示例:
# ================================================================================
# LOAD TEST CONFIGURATION
# ================================================================================
# 
# Application Configuration:
#   Default Provider:    openrouter (fallback)
#   Default Model:       google/gemini-2.0-flash-lite-001 (fallback)
# 
# Actual LLM Configuration (from core/llm_adapter/config.yaml):
#   Default Provider:    openrouter
#   Cheap Model:         google/gemini-2.0-flash-lite-001
#   Normal Model:        google/gemini-2.0-flash-lite-001
#   Premium Model:       google/gemini-2.0-flash-lite-001
#   Multimodal Model:    qwen/qwen3-vl-30b-a3b-instruct
# 
# Merge Step Configuration:
#   USE_MERGE_STEP:      False
# ================================================================================
```

### 启用 Prompt Logging

```bash
# 方式 1: 环境变量
export TRACE_ENABLED=true
export TRACE_LOG_LLM_PROMPT=true
export USE_MERGE_STEP=true

# 方式 2: 启动脚本
./start_server.sh --log-prompt

# 查看日志
tail -f logs/trace.jsonl | grep merge_step
```

### 运行 Load Test

```bash
# 基础测试
python tests/load_test.py \
  --concurrent 10 \
  --requests 100 \
  --image-url https://test-r2.zhizitech.org/test_discord_2.png

# 禁用缓存测试
python tests/load_test.py \
  --concurrent 10 \
  --requests 100 \
  --image-url https://test-r2.zhizitech.org/test_discord_2.png \
  --disable-cache
```

## 测试验证

```bash
# 1. 验证 prompt logging
export TRACE_ENABLED=true
export TRACE_LOG_LLM_PROMPT=true
export USE_MERGE_STEP=true
python main.py
# 发送请求后检查 logs/trace.jsonl

# 2. 验证代码清理
python -m py_compile app/api/v1/predict.py
# 应该没有语法错误

# 3. 验证配置显示
python tests/load_test.py --help
# 应该显示实际配置信息
```

## 相关文档

- **配置说明**: `dev-docs/LLM_CONFIG_CLARIFICATION.md` ⭐ 新建
- **Trace Logging**: `dev-docs/TRACE_LOGGING_IMPLEMENTATION.md`
- **Merge Step**: `dev-docs/MERGE_STEP_INTEGRATION.md`

## 总结

### 修改的文件

1. ✅ `app/services/orchestrator.py` - 添加 merge_step prompt logging
2. ✅ `app/api/v1/predict.py` - 删除 `handle_image_old()` 函数
3. ✅ `tests/load_test.py` - 添加配置信息打印
4. ✅ `app/core/config.py` - 添加配置说明注释
5. ✅ `dev-docs/LLM_CONFIG_CLARIFICATION.md` - 新建配置说明文档

### 影响范围

- **Prompt Logging**: merge_step 现在支持 `--log-prompt` 参数
- **代码清理**: 删除约 300 行未使用的代码
- **调试改进**: load test 自动显示实际配置
- **配置清晰**: 明确区分 fallback 配置和实际配置

### 向后兼容性

✅ **完全向后兼容**

- 所有修改都是增强功能，不影响现有行为
- 删除的函数未被使用，不影响任何功能
- 配置打印是可选的，不影响测试执行
- 配置说明只是注释，不改变行为

---

**更新日期**: 2026-02-05
**版本**: v1.1
**状态**: ✅ 完成
