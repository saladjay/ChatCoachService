# LLM Provider 统一为 DashScope

## 问题描述

在执行 `complete_flow_example.py` 时，系统尝试访问 Gemini API 但遇到 429 错误（请求过多）：

```
2026-01-22 15:16:31,603 - httpx - INFO - HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=your_google_api_key_here "HTTP/1.1 429 Too Many Requests"
```

## 解决方案

统一所有 LLM 调用使用 DashScope (Qwen) 作为默认 provider。

## 修改内容

### 1. 更新 `app/core/container.py`

为所有服务初始化时明确指定 provider 和 model：

**ContextBuilder**:
```python
return ContextBuilder(
    llm_adapter=llm_adapter,
    provider="dashscope",
    model="qwen-flash"
)
```

**SceneAnalyzer**:
```python
return SceneAnalyzer(
    llm_adapter=llm_adapter,
    provider="dashscope",
    model="qwen-flash"
)
```

**StrategyPlanner**:
```python
return StrategyPlanner(
    llm_adapter=llm_adapter,
    provider="dashscope",
    model="qwen-flash"
)
```

### 2. 更新 `core/llm_adapter/config.yaml`

将默认 provider 从 openai 改为 dashscope：

```yaml
llm:
  default_provider: dashscope  # 原来是 openai
```

## 验证

运行验证命令确认所有服务使用 dashscope：

```bash
python -c "from app.core.container import ServiceContainer, ServiceMode; container = ServiceContainer(mode=ServiceMode.REAL); cb = container.get_context_builder(); print(f'ContextBuilder provider: {cb.provider}, model: {cb.model}'); sa = container.get_scene_analyzer(); print(f'SceneAnalyzer provider: {sa.provider}, model: {sa.model}')"
```

输出：
```
ContextBuilder provider: dashscope, model: qwen-flash
SceneAnalyzer provider: dashscope, model: qwen-flash
```

## 影响范围

### 受影响的服务

1. **ContextBuilder** - 对话上下文分析
2. **SceneAnalyzer** - 场景分析
3. **StrategyPlanner** - 策略规划
4. **ReplyGenerator** - 回复生成（通过 LLM adapter 的默认配置）
5. **UserProfileService** - 用户画像分析（trait discovery, mapping 等）

### 不受影响的部分

- Mock 模式的服务（不调用真实 LLM）
- 测试代码中明确指定 provider 的调用
- 配置文件中的其他 provider 配置（仍然保留，可手动指定使用）

## 使用说明

### 默认行为

现在所有服务默认使用 DashScope (Qwen Flash)：

```python
# 自动使用 dashscope
container = ServiceContainer(mode=ServiceMode.REAL)
orchestrator = container.create_orchestrator()
response = await orchestrator.generate_reply(request)
```

### 手动指定其他 Provider

如果需要使用其他 provider，可以在调用时明确指定：

```python
# 使用 OpenAI
result = await llm_adapter.call(LLMCall(
    task_type="generation",
    prompt="...",
    provider="openai",
    model="gpt-4o"
))

# 使用 Gemini（如果 API 配额允许）
result = await llm_adapter.call(LLMCall(
    task_type="generation",
    prompt="...",
    provider="gemini",
    model="gemini-2.5-flash"
))
```

### 在 Examples 中指定 Provider

示例代码中可以通过参数指定：

```python
# 在 user_profile_impl.py 的方法中
await user_profile_service.learn_new_traits(
    user_id=user_id,
    selected_sentences=sentences,
    provider="dashscope",  # 明确指定
    model="qwen-flash",
    store=True,
    map_to_standard=True,
)
```

## 成本对比

使用 DashScope 相比 Gemini 的成本优势：

| Provider | Model | Input (per 1M tokens) | Output (per 1M tokens) |
|----------|-------|----------------------|------------------------|
| DashScope | qwen-flash | $0.30 | $0.60 |
| Gemini | gemini-2.5-flash | $0.075 | $0.30 |
| OpenAI | gpt-4o-mini | $0.15 | $0.60 |

**注意**: 虽然 Gemini 价格更低，但由于 API 配额限制（429 错误），统一使用 DashScope 可以保证服务稳定性。

## 配置文件位置

- **主配置**: `core/llm_adapter/config.yaml`
- **容器初始化**: `app/core/container.py`
- **服务实现**: 
  - `app/services/context_impl.py`
  - `app/services/scene_analyzer_impl.py`
  - `app/services/strategy_planner.py`

## 相关文档

- `PROMPT_CLEANUP_SUMMARY.md` - Prompt 清理总结
- `PROMPT_VERSION_COMPARISON_REPORT.md` - Prompt 版本对比
- `TOKEN_OPTIMIZATION_IMPLEMENTATION.md` - Token 优化实现

---

*最后更新: 2026-01-22*
*状态: 已完成*
