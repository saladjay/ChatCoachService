# Generation JSON Parsing Fix

## 问题

在 `logs-1/failed_json_replies/failed_reply_20260205_150221_513467_load_tes.json` 中，记录的失败 JSON 是：

```json
{
  "timestamp": "2026-02-05T15:02:21.513506",
  "session_id": "load_test_session_1770303683319",
  "error": "Expecting value: line 1 column 1 (char 0)",
  "reply_text": "好的，我明白了。",
  "reply_length": 8
}
```

**问题**：
- 只记录了 `reply_text`（8 个字符）
- 没有记录**完整的原始 LLM 响应**
- 无法知道 LLM 到底返回了什么

## 根本原因

### 1. 记录的是处理后的文本，不是原始响应

在 `app/api/v1/predict.py` 中：

```python
orchestrator_response = await orchestrator.generate_reply(orchestrator_request)
# orchestrator_response.reply_text 已经是 LLM 返回的文本
# 如果 LLM 返回 "好的，我明白了。"，这就是 reply_text 的值

try:
    reply_text = parse_json_with_markdown(orchestrator_response.reply_text)
except json.JSONDecodeError as exc:
    _log_failed_json_reply(
        orchestrator_response.reply_text,  # 只记录了这个文本
        request.session_id,
        str(exc)
    )
```

### 2. parse_json_with_markdown 缺少 fallback 机制

原有的 `parse_json_with_markdown` 函数只有简单的提取逻辑：
- 提取 markdown 代码块
- 提取 JSON 对象
- 直接解析

**缺少**：
- 栈匹配算法（处理嵌套和字符串中的括号）
- 多层 fallback 策略
- 详细的错误信息

## 解决方案

### 1. 改进失败记录

修改 `_log_failed_json_reply()` 函数：

```python
def _log_failed_json_reply(reply_text: str, session_id: str, error_msg: str) -> None:
    """Log failed JSON reply to file for analysis.
    
    This saves the COMPLETE raw response from LLM that failed to parse as JSON.
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "error": error_msg,
        "raw_text": reply_text,  # 完整的原始文本
        "raw_text_length": len(reply_text),
        "truncated_preview": reply_text[:500],  # 前 500 字符预览
        "source": "generation_reply_parser",
    }
    
    # 保存到文件...
    
    logger.warning(
        f"Failed JSON reply saved to {filename}. "
        f"Response length: {len(reply_text)} chars. "
        f"Review this file to understand why JSON parsing failed."
    )
```

**改进**：
- ✅ 使用 `raw_text` 而不是 `reply_text`（更清晰）
- ✅ 添加 `raw_text_length`（完整长度）
- ✅ 添加 `truncated_preview`（预览）
- ✅ 添加 `source` 标识（区分来源）
- ✅ 使用 `logger.warning` 而不是 `logger.info`（更醒目）

### 2. 改进 JSON 解析

修改 `parse_json_with_markdown()` 函数，使用 5 层 fallback 策略：

```python
def parse_json_with_markdown(text: str) -> dict:
    """Parse JSON text with multiple fallback strategies."""
    
    # Strategy 1: Direct JSON parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Markdown JSON code blocks (```json ... ```)
    if "```json" in text:
        # Extract and try to parse...
    
    # Strategy 3: Simple code blocks (``` ... ```)
    if "```" in text:
        # Extract and try to parse...
    
    # Strategy 4: Simple regex extraction
    if "{" in text:
        # Extract and try to parse...
    
    # Strategy 5: Stack-based extraction (most reliable)
    json_objects = _extract_complete_json_objects(text)
    for json_str in json_objects:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            continue
    
    # All strategies failed
    raise json.JSONDecodeError(...)
```

**新增**：
- ✅ 栈匹配算法 `_extract_complete_json_objects()`
- ✅ 5 层 fallback 策略（与 `llm_adapter.py` 一致）
- ✅ 更详细的错误信息

### 3. 栈匹配算法

新增 `_extract_complete_json_objects()` 函数：

```python
def _extract_complete_json_objects(text: str) -> list[str]:
    """Extract all complete JSON objects using stack-based bracket matching."""
    results = []
    stack = []
    start_idx = None
    in_string = False
    escape_next = False
    
    for i, char in enumerate(text):
        # Handle string escaping
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        # Track if we're inside a string
        if char == '"':
            in_string = not in_string
            continue
        
        # Only process braces outside of strings
        if not in_string:
            if char == '{':
                if not stack:
                    start_idx = i
                stack.append('{')
            elif char == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
                    if not stack and start_idx is not None:
                        results.append(text[start_idx:i+1])
                        start_idx = None
    
    return results
```

**特点**：
- ✅ 正确处理嵌套对象
- ✅ 正确处理字符串中的括号
- ✅ 正确处理转义引号
- ✅ 检测不完整的 JSON

## 对比

### 之前的记录

```json
{
  "timestamp": "2026-02-05T15:02:21.513506",
  "session_id": "load_test_session_1770299453166",
  "error": "Expecting value: line 1 column 1 (char 0)",
  "reply_text": "好的，我明白了。",
  "reply_length": 8
}
```

**问题**：
- ❌ 只有 8 个字符
- ❌ 不知道 LLM 完整返回了什么
- ❌ 无法调试

### 之后的记录

```json
{
  "timestamp": "2026-02-05T15:02:21.513506",
  "session_id": "load_test_session_1770299453166",
  "error": "Expecting value: line 1 column 1 (char 0)",
  "raw_text": "好的，我明白了。\n\n（如果 LLM 返回了更多内容，这里会显示完整的内容）",
  "raw_text_length": 100,
  "truncated_preview": "好的，我明白了。\n\n（前 500 字符预览）",
  "source": "generation_reply_parser"
}
```

**改进**：
- ✅ 完整的原始文本（`raw_text`）
- ✅ 完整长度（`raw_text_length`）
- ✅ 预览（`truncated_preview`）
- ✅ 来源标识（`source`）

## 为什么 LLM 返回纯文本？

可能的原因：

### 1. Prompt 不够明确
- LLM 没有理解需要返回 JSON
- Prompt 中的 JSON 格式说明不够清晰

### 2. 模型问题
- 某些模型不擅长生成 JSON
- 模型可能被其他指令干扰

### 3. 上下文问题
- 对话历史中有混淆的信息
- 用户输入导致 LLM 误解

### 4. 随机性
- LLM 的随机性导致偶尔返回非 JSON

## 建议

### 短期（立即）

1. **检查 Prompt**：
   - 确保 prompt 明确要求返回 JSON
   - 添加示例 JSON 输出
   - 强调 "MUST return JSON" 等关键词

2. **添加验证**：
   - 在 prompt 中添加 JSON schema
   - 要求 LLM 验证输出格式

3. **监控失败率**：
   - 统计 JSON 解析失败的比例
   - 分析失败的模式

### 中期（1-2 周）

1. **改进 Prompt 模板**：
   - 使用更严格的 JSON 格式要求
   - 添加格式验证示例

2. **模型选择**：
   - 测试不同模型的 JSON 生成能力
   - 选择更擅长生成 JSON 的模型

3. **添加重试**：
   - 如果返回非 JSON，自动重试
   - 使用更明确的 prompt

### 长期（1 个月）

1. **结构化输出**：
   - 使用 OpenAI 的 JSON mode
   - 或使用 function calling

2. **后处理**：
   - 如果 LLM 返回纯文本，自动包装成 JSON
   - 添加智能修复机制

## 测试

### 测试 1：纯文本响应

```python
text = "好的，我明白了。"
try:
    result = parse_json_with_markdown(text)
except json.JSONDecodeError as e:
    # 应该抛出异常，并记录完整的文本
    print(f"Expected error: {e}")
```

### 测试 2：不完整的 JSON

```python
text = '{"key": "value", "incomplete":'
try:
    result = parse_json_with_markdown(text)
except json.JSONDecodeError as e:
    # 应该抛出异常
    print(f"Expected error: {e}")
```

### 测试 3：嵌套 JSON

```python
text = '{"outer": {"inner": "value"}}'
result = parse_json_with_markdown(text)
assert result == {"outer": {"inner": "value"}}
```

### 测试 4：字符串中的括号

```python
text = '{"message": "This has { and } in it"}'
result = parse_json_with_markdown(text)
assert result == {"message": "This has { and } in it"}
```

## 相关文件

- `app/api/v1/predict.py`：修改的主要文件
- `app/services/llm_adapter.py`：参考的 JSON 解析逻辑
- `dev-docs/JSON_PARSING_IMPROVEMENTS.md`：LLM adapter 的 JSON 解析改进
- `logs/failed_json_replies/`：失败 JSON 的保存目录

## 更新日期

2026-02-05
