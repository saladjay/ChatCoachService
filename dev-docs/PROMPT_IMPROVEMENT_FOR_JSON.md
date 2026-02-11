# Prompt Improvement for JSON Output

## 问题

LLM 有时返回纯文本而不是 JSON：
```
"好的，我明白了。"
```

而不是期望的：
```json
{
  "replies": [
    {"text": "...", "strategy": "...", "reasoning": "..."}
  ]
}
```

## 根本原因

### 1. Prompt 不够强调 JSON 格式

当前 prompt（`reply_generation_v3.0-compact.txt`）：
```
Output JSON:
{
  "replies": [
    {"text": "...", "strategy": "...", "reasoning": "..."}
  ]
}
```

**问题**：
- 只说了 "Output JSON"，没有强调**必须**返回 JSON
- 没有说明如果返回非 JSON 会怎样
- 没有提供足够的示例

### 2. 模型可能被其他指令干扰

- 对话历史中可能有混淆的信息
- 用户输入可能导致 LLM 误解
- 模型的随机性

### 3. 某些模型不擅长生成 JSON

- 不同模型对 JSON 格式的理解不同
- 某些模型更倾向于自然语言回复

## 解决方案

### 方案 1：改进 Prompt（推荐）

#### 改进后的 Prompt

```
Professional dating coach. Generate 3 reply suggestions.

## Context
Scenario: {recommended_scenario}
Strategies: {recommended_strategies}
Intimacy: User({intimacy_level}) vs Current({current_intimacy_level})
Emotion: {emotion_state}

## Summary
{conversation_summary}

## User Style
{user_style_compact}

## Last Message
{last_message}

## Language
{language}

## CRITICAL: Output Format

You MUST respond with ONLY valid JSON in the following format.
Do NOT include any explanatory text before or after the JSON.
Do NOT wrap the JSON in markdown code blocks.

Required JSON structure:
{{
  "replies": [
    {{"text": "reply text here", "strategy": "strategy_code", "reasoning": "brief explanation"}},
    {{"text": "reply text here", "strategy": "strategy_code", "reasoning": "brief explanation"}},
    {{"text": "reply text here", "strategy": "strategy_code", "reasoning": "brief explanation"}}
  ]
}}

Example output:
{{
  "replies": [
    {{"text": "That sounds amazing! I'm so happy for you.", "strategy": "empathetic_ack", "reasoning": "Acknowledge positive emotion"}},
    {{"text": "Where did you go? I'd love to hear more about it!", "strategy": "open_question", "reasoning": "Show interest and encourage sharing"}},
    {{"text": "You deserve it! Hope you had a great time.", "strategy": "appreciation", "reasoning": "Validate and support"}}
  ]
}}

IMPORTANT: Your response must be ONLY the JSON object above. No other text.
```

**改进点**：
- ✅ 使用 "CRITICAL" 和 "MUST" 强调重要性
- ✅ 明确说明不要包含其他文本
- ✅ 提供完整的示例
- ✅ 重复强调 "ONLY JSON"

### 方案 2：使用 System Prompt

在 system prompt 中强调 JSON 格式：

```python
system_prompt = """You are a professional dating coach AI assistant.

CRITICAL RULE: You MUST ALWAYS respond with valid JSON format.
NEVER respond with plain text or explanations outside of JSON.
If you cannot generate a proper response, return an error in JSON format:
{"error": "reason for failure"}

Your responses must be parseable by json.loads() in Python.
"""
```

### 方案 3：使用 OpenAI JSON Mode

如果使用 OpenAI 模型，启用 JSON mode：

```python
llm_call = LLMCall(
    task_type="generation",
    prompt=prompt,
    quality=quality,
    user_id=user_id,
    response_format={"type": "json_object"}  # OpenAI JSON mode
)
```

### 方案 4：使用 Function Calling

定义 function schema：

```python
function_schema = {
    "name": "generate_replies",
    "description": "Generate reply suggestions",
    "parameters": {
        "type": "object",
        "properties": {
            "replies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "strategy": {"type": "string"},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["text", "strategy", "reasoning"]
                }
            }
        },
        "required": ["replies"]
    }
}
```

### 方案 5：后处理 - 智能包装

如果 LLM 返回纯文本，自动包装成 JSON：

```python
def wrap_plain_text_as_json(text: str) -> dict:
    """Wrap plain text response as JSON."""
    if not text.strip().startswith('{'):
        # Plain text detected, wrap it
        return {
            "replies": [
                {
                    "text": text.strip(),
                    "strategy": "direct_response",
                    "reasoning": "LLM returned plain text, wrapped automatically"
                }
            ]
        }
    return json.loads(text)
```

## 推荐实施顺序

### 短期（立即）

1. **改进 Prompt**：
   - 添加 "CRITICAL" 和 "MUST" 关键词
   - 提供完整的 JSON 示例
   - 强调 "ONLY JSON"

2. **添加后处理**：
   - 检测纯文本响应
   - 自动包装成 JSON
   - 记录警告日志

### 中期（1-2 周）

3. **添加 System Prompt**：
   - 在 system message 中强调 JSON 格式
   - 提供错误处理指南

4. **测试不同模型**：
   - 比较不同模型的 JSON 生成能力
   - 选择最擅长 JSON 的模型

### 长期（1 个月）

5. **使用结构化输出**：
   - OpenAI JSON mode
   - Function calling
   - Structured outputs

6. **添加验证**：
   - 在 prompt 中添加 JSON schema
   - 要求 LLM 自我验证

## 改进后的 Prompt 模板

创建新版本：`prompts/versions/reply_generation_v3.1-compact-strict-json.txt`

```
Professional dating coach. Generate 3 reply suggestions.

## Context
Scenario: {recommended_scenario}
Strategies: {recommended_strategies}
Intimacy: User({intimacy_level}) vs Current({current_intimacy_level})
Emotion: {emotion_state}

## Summary
{conversation_summary}

## User Style
{user_style_compact}

## Last Message
{last_message}

## Language
{language}

## ⚠️ CRITICAL: JSON Output Format

You MUST respond with ONLY valid JSON. No explanations, no markdown, no extra text.

Required structure:
{{
  "replies": [
    {{"text": "...", "strategy": "...", "reasoning": "..."}},
    {{"text": "...", "strategy": "...", "reasoning": "..."}},
    {{"text": "...", "strategy": "...", "reasoning": "..."}}
  ]
}}

Example (copy this structure):
{{
  "replies": [
    {{"text": "That's wonderful! I'm so happy for you.", "strategy": "empathetic_ack", "reasoning": "Acknowledge positive emotion"}},
    {{"text": "Where did you go? Tell me more!", "strategy": "open_question", "reasoning": "Show interest"}},
    {{"text": "You deserve it! Hope it was amazing.", "strategy": "appreciation", "reasoning": "Validate"}}
  ]
}}

⚠️ IMPORTANT: Output ONLY the JSON object. Nothing else.
```

## 测试

### 测试 1：正常 JSON 响应

```python
response = '{"replies": [{"text": "Great!", "strategy": "empathetic_ack", "reasoning": "Positive"}]}'
result = parse_json_with_markdown(response)
assert "replies" in result
```

### 测试 2：纯文本响应（应该被包装）

```python
response = "好的，我明白了。"
result = wrap_plain_text_as_json(response)
assert result == {
    "replies": [{
        "text": "好的，我明白了。",
        "strategy": "direct_response",
        "reasoning": "LLM returned plain text, wrapped automatically"
    }]
}
```

### 测试 3：Markdown 包装的 JSON

```python
response = '```json\n{"replies": [...]}\n```'
result = parse_json_with_markdown(response)
assert "replies" in result
```

## 监控

### 添加指标

```python
# 在 orchestrator.py 中
if not text.strip().startswith('{'):
    logger.warning(
        f"LLM returned plain text instead of JSON. "
        f"Provider: {provider}, Model: {model}, "
        f"Text: {text[:100]}"
    )
    metrics.increment("llm.plain_text_response")
```

### 定期分析

```bash
# 统计纯文本响应的比例
grep "plain text instead of JSON" logs/app.log | wc -l
```

## 相关文件

- `prompts/versions/reply_generation_v3.0-compact.txt`：当前 prompt
- `prompts/versions/reply_generation_v3.1-compact-strict-json.txt`：改进后的 prompt（待创建）
- `app/api/v1/predict.py`：JSON 解析逻辑
- `scripts/extract_failed_json_from_trace.py`：失败 JSON 分析工具

## 更新日期

2026-02-05
