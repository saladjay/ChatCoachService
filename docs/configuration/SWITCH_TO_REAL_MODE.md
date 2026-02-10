# Switch from Mock to Real Mode

## 问题描述

系统使用的是 `MockReplyGenerator`，返回模拟数据：

```
reply_generator <class 'app.services.mocks.MockReplyGenerator'>
reply_result text='这是一个模拟回复，用于开发和测试。' provider='openai' model='gpt-4' input_tokens=100 output_tokens=50 cost_usd=0.01
```

## 根本原因

`get_container()` 函数创建 `ServiceContainer` 时没有指定 `mode` 参数，默认使用 `ServiceMode.MOCK`：

```python
def get_container() -> ServiceContainer:
    global _container
    if _container is None:
        _container = ServiceContainer()  # 默认 mode=ServiceMode.MOCK
    return _container
```

## 解决方案

修改 `get_container()` 函数，明确指定使用 `ServiceMode.REAL`：

```python
def get_container() -> ServiceContainer:
    """Get the global service container instance.
    
    Creates a new container if one doesn't exist.
    Uses REAL mode by default for production use.
    
    Returns:
        The global ServiceContainer instance.
    """
    global _container
    if _container is None:
        _container = ServiceContainer(mode=ServiceMode.REAL)
    return _container
```

## 影响

切换到 REAL 模式后，所有服务都将使用真实实现：

### 1. Reply Generator
- ❌ Mock: `MockReplyGenerator` - 返回固定的模拟回复
- ✅ Real: `LLMAdapterReplyGenerator` - 使用 LLM 生成真实回复

### 2. Scene Analyzer
- ❌ Mock: `MockSceneAnalyzer` - 返回固定的场景分析
- ✅ Real: `SceneAnalyzer` - 使用 LLM 分析真实场景

### 3. Persona Inferencer
- ❌ Mock: `MockPersonaInferencer` - 返回固定的人格推断
- ✅ Real: `UserProfilePersonaInferencer` - 基于用户画像推断人格

### 4. Context Builder
- ❌ Mock: `MockContextBuilder` - 返回固定的上下文
- ✅ Real: `ContextBuilder` - 构建真实的对话上下文

### 5. Intimacy Checker
- ❌ Mock: `MockIntimacyChecker` - 返回固定的亲密度检查结果
- ✅ Real: `ModerationServiceIntimacyChecker` - 使用审核服务检查亲密度

## 配置要求

使用 REAL 模式需要配置以下内容：

### 1. LLM Adapter 配置

在 `core/llm_adapter/config.yaml` 中配置 API 密钥：

```yaml
providers:
  gemini:
    api_key: YOUR_GEMINI_API_KEY
    models:
      cheap: gemini-2.5-flash
      normal: gemini-2.5-flash
      premium: gemini-2.5-flash

  dashscope:
    api_key: YOUR_DASHSCOPE_API_KEY
    base_url: https://dashscope.aliyuncs.com/api/v1
    models:
      cheap: qwen-flash
      normal: qwen-flash
      premium: qwen-flash

  openrouter:
    api_key: YOUR_OPENROUTER_API_KEY
    base_url: https://openrouter.ai/api/v1
    models:
      cheap: google/gemini-2.0-flash-001
      normal: google/gemini-2.5-flash
      premium: google/gemini-3-flash-preview
```

### 2. 数据库配置

在 `.env` 文件中配置数据库连接：

```env
DATABASE_URL=sqlite+aiosqlite:///./conversation.db
```

### 3. 审核服务配置（可选）

在 `config.yaml` 中配置审核服务：

```yaml
moderation:
  base_url: http://your-moderation-service
  timeout_seconds: 30
  policy: default
  fail_open: true
```

## 验证

重启服务后，检查日志应该看到：

```
INFO - ServiceContainer initialized with mode: real
INFO - Using LLMAdapterReplyGenerator for reply generation
INFO - Using SceneAnalyzer for scene analysis
```

而不是：

```
INFO - ServiceContainer initialized with mode: mock
INFO - Using MockReplyGenerator for reply generation
```

## 回滚

如果需要回到 Mock 模式（例如测试环境），可以：

1. **临时回滚**: 修改 `get_container()` 函数
   ```python
   _container = ServiceContainer(mode=ServiceMode.MOCK)
   ```

2. **环境变量控制**: 可以添加环境变量支持
   ```python
   import os
   mode = ServiceMode.REAL if os.getenv("USE_REAL_SERVICES", "true").lower() == "true" else ServiceMode.MOCK
   _container = ServiceContainer(mode=mode)
   ```

## 相关文件

- `app/core/container.py` - 修改了 `get_container()` 函数
- `core/llm_adapter/config.yaml` - LLM 配置
- `config.yaml` - 应用配置

## 注意事项

1. **API 成本**: 使用真实 LLM 会产生 API 调用费用
2. **响应时间**: 真实 LLM 调用比 Mock 慢
3. **依赖服务**: 需要确保所有外部服务（LLM、数据库等）可用
4. **错误处理**: 真实模式下需要处理更多的错误情况（网络错误、API 限流等）

## 测试

可以通过以下方式测试 REAL 模式：

```bash
# 重启服务
python -m uvicorn app.main:app --reload

# 调用 predict 端点
curl -X POST "http://localhost:8000/api/v1/ChatCoach/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "content": ["http://example.com/screenshot.jpg"],
    "language": "zh",
    "scene": 1,
    "user_id": "test_user",
    "session_id": "test_session",
    "reply": true
  }'
```

应该返回真实的 LLM 生成的回复，而不是模拟数据。
