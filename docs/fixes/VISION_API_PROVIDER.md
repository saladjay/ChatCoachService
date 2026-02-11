# Vision API Provider 配置修复

## 问题描述

错误信息：
```
Error 1002: LLM API call failed: Vision API call failed: API error:
```

## 根本原因

1. **DashScope adapter 不支持 vision/multimodal 功能**
   - DashScope adapter 只实现了文本生成 API
   - 没有实现图像分析（vision）功能
   - 配置中虽然指定了 `multimodal: qwen3-vl-30b-a3b-instruct`，但 adapter 代码中没有实现

2. **默认 provider 配置问题**
   - `config.yaml` 中 `default_provider: dashscope`
   - 当调用 screenshot 分析时，系统尝试使用 DashScope
   - DashScope adapter 无法处理 vision 请求，导致失败

## 解决方案

### 方案 1：使用 Gemini 作为 Multimodal Provider（已实施）

在 `.env` 文件中添加：

```bash
# Multimodal LLM Configuration
# DashScope doesn't support vision yet, so use Gemini for screenshot analysis
MULTIMODAL_DEFAULT_PROVIDER=gemini
```

**优点：**
- Gemini 完全支持 vision 功能
- 已经配置好 Vertex AI 认证
- 性能稳定，配额充足

**配置检查：**
```yaml
# core/llm_adapter/config.yaml
gemini:
  api_key: AIzaSyD2QJpLm36fthlDDVebQsgr-4ddnAoD1Dg
  mode: vertex
  project_id: wingy-e87ee
  location: global
  models:
    multimodal: gemini-2.0-flash-lite-001
```

### 方案 2：使用 OpenRouter 作为 Multimodal Provider

在 `.env` 文件中设置：

```bash
MULTIMODAL_DEFAULT_PROVIDER=openrouter
```

**优点：**
- 支持多种 vision 模型
- 已配置 API key
- 可以使用不同的模型

**配置检查：**
```yaml
# core/llm_adapter/config.yaml
openrouter:
  api_key: ${OPENROUTER_API_KEY}
  base_url: ${OPENROUTER_BASE_URL}
  models:
    multimodal: google/gemini-2.0-flash-lite-001
```

### 方案 3：为 DashScope 实现 Vision 支持（长期方案）

需要在 `core/llm_adapter/llm_adapter/adapters/dashscope_adapter.py` 中实现 vision API 调用。

参考 DashScope 官方文档：
- https://help.aliyun.com/zh/dashscope/developer-reference/tongyi-qianwen-vl-plus-api

## 验证修复

### 1. 检查配置

```bash
# 查看 .env 文件
cat .env | grep MULTIMODAL_DEFAULT_PROVIDER

# 应该输出：
# MULTIMODAL_DEFAULT_PROVIDER=gemini
```

### 2. 重启服务

```bash
python main.py
```

### 3. 测试 Screenshot 分析

```bash
curl -X POST http://localhost:8000/api/v1/ChatCoach/predict \
  -H "Content-Type: application/json" \
  -d '{
    "content": ["http://example.com/screenshot.jpg"],
    "scene": 1,
    "user_id": "test_user",
    "session_id": "test_session"
  }'
```

### 4. 检查日志

应该看到：
```
Using provider: gemini for multimodal task
```

而不是：
```
Vision API call failed: API error:
```

## Provider 功能对比

| Provider | Text Generation | Vision/Multimodal | 状态 |
|----------|----------------|-------------------|------|
| DashScope | ✅ 支持 | ❌ 未实现 | 仅文本 |
| Gemini | ✅ 支持 | ✅ 支持 | 推荐用于 vision |
| OpenRouter | ✅ 支持 | ✅ 支持 | 备选方案 |
| OpenAI | ✅ 支持 | ✅ 支持 | 需要配置 |

## 注意事项

1. **DashScope 仍然用于文本生成**
   - `default_provider: dashscope` 保持不变
   - 只有 vision 任务使用 Gemini

2. **API Key 检查**
   - 确保 Gemini API key 有效
   - 确保 Vertex AI 认证文件存在

3. **代理配置**
   - 如果使用代理，确保 Gemini 可以访问
   - 检查 `config.yaml` 中的 proxy 配置

4. **成本考虑**
   - Gemini vision 调用有成本
   - 监控 API 使用量

## 相关文件

- `.env`: 环境变量配置
- `core/llm_adapter/config.yaml`: LLM adapter 配置
- `core/llm_adapter/llm_adapter/adapters/dashscope_adapter.py`: DashScope adapter 实现
- `core/llm_adapter/llm_adapter/adapters/gemini_adapter.py`: Gemini adapter 实现
- `app/services/llm_adapter.py`: LLM adapter 主服务

## 未来改进

1. **实现 DashScope Vision 支持**
   - 添加 `call_vision` 方法到 DashScope adapter
   - 支持 `qwen3-vl-30b-a3b-instruct` 模型

2. **自动 Provider 选择**
   - 根据任务类型自动选择最佳 provider
   - 实现 provider 降级策略

3. **统一 Vision API 接口**
   - 标准化所有 provider 的 vision API 调用
   - 简化配置和使用
