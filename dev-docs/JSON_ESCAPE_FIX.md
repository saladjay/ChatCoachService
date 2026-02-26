# JSON 解析修复：无效转义序列

## 问题描述

在 2026-02-11 的日志中发现，LLM 返回的 JSON 包含无效的转义序列，导致 JSON 解析失败：

```
Failed to parse reply text as JSON: Invalid \escape: line 3 column 57 (char 67)
```

### 问题示例

LLM 返回的 JSON：
```json
{
  "r": [
    ["Okay, but promise you won't judge my silly posts! \[calm_presence, low_pressure_invite]", "calm_presence, low_pressure_invite"]
  ]
}
```

问题：`\[` 和 `\]` 是无效的 JSON 转义序列。

### 有效的 JSON 转义序列

根据 JSON 规范（RFC 8259），只有以下转义序列是有效的：

| 转义序列 | 含义 |
|---------|------|
| `\"` | 双引号 |
| `\\` | 反斜杠 |
| `\/` | 斜杠 |
| `\b` | 退格 |
| `\f` | 换页 |
| `\n` | 换行 |
| `\r` | 回车 |
| `\t` | 制表符 |
| `\uXXXX` | Unicode 字符 |

其他字符（如 `[`, `]`, `(`, `)`, `{`, `}`）不需要转义，也不应该被转义。

## 根本原因

LLM（特别是某些模型）有时会错误地转义不需要转义的字符，可能是因为：

1. 训练数据中包含了错误的转义示例
2. 模型过度谨慎，试图转义所有特殊字符
3. 某些编程语言（如正则表达式）中需要转义这些字符，模型混淆了不同的转义规则

## 解决方案

在 `_repair_json_string()` 函数中添加了 Step 8，用于移除无效的转义序列：

```python
# Step 8: Fix invalid escape sequences
# Remove backslashes before characters that don't need escaping in JSON
# Valid JSON escapes: \" \\ \/ \b \f \n \r \t \uXXXX
# Invalid escapes that LLMs sometimes add: \[ \] \( \) etc.
text = re.sub(r'\\([^\"\\/bfnrtu])', r'\1', text)
```

### 正则表达式解释

- `\\([^\"\\/bfnrtu])`：匹配反斜杠后跟一个不是有效转义字符的字符
  - `\\`：匹配反斜杠
  - `([^\"\\/bfnrtu])`：捕获组，匹配任何不是 `"`, `\`, `/`, `b`, `f`, `n`, `r`, `t`, `u` 的字符
- `r'\1'`：替换为捕获的字符（移除反斜杠）

### 处理逻辑

1. **保留有效转义**：`\"`, `\\`, `\/`, `\b`, `\f`, `\n`, `\r`, `\t`, `\uXXXX` 保持不变
2. **移除无效转义**：`\[`, `\]`, `\(`, `\)`, `\{`, `\}` 等转换为 `[`, `]`, `(`, `)`, `{`, `}`

## 测试验证

创建了测试脚本 `scripts/test_json_escape_fix.py` 来验证修复：

### 测试用例 1：真实问题场景

**输入：**
```json
{"r": [["Okay, but promise you won't judge my silly posts! \[calm_presence, low_pressure_invite]", "calm_presence, low_pressure_invite"]]}
```

**输出：**
```json
{"r": [["Okay, but promise you won't judge my silly posts! [calm_presence, low_pressure_invite]", "calm_presence, low_pressure_invite"]]}
```

✅ 解析成功，方括号被正确保留（无反斜杠）

### 测试用例 2：简单转义方括号

**输入：**
```json
{"text": "Use strategy \[A\] or \[B\]"}
```

**输出：**
```json
{"text": "Use strategy [A] or [B]"}
```

✅ 方括号正确去转义

### 测试用例 3：混合有效和无效转义

**输入：**
```json
{"text": "Line 1\nLine 2\t\[tag\]", "quote": "He said \"hello\""}
```

**输出：**
```json
{"text": "Line 1\nLine 2\t[tag]", "quote": "He said \"hello\""}
```

✅ 有效转义（`\n`, `\t`, `\"`）保留，无效转义（`\[`, `\]`）移除

### 测试用例 4：其他无效转义

**输入：**
```json
{"text": "Parentheses \(like this\) and \{braces\}"}
```

**输出：**
```json
{"text": "Parentheses (like this) and {braces}"}
```

✅ 所有无效转义移除

## 运行测试

```bash
python scripts/test_json_escape_fix.py
```

预期输出：
```
Testing JSON parsing with invalid escape sequences...
============================================================
...
✅ All tests passed!
```

## 影响范围

### 修改的文件

- `app/api/v1/predict.py`：在 `_repair_json_string()` 函数中添加 Step 8

### 影响的功能

- Reply generation：修复了 LLM 返回包含无效转义的 JSON 时的解析失败问题
- 所有使用 `parse_json_with_markdown()` 的地方都会受益于这个修复

### 向后兼容性

✅ 完全向后兼容：
- 有效的 JSON 不受影响
- 有效的转义序列保持不变
- 只移除无效的转义序列

## 相关日志

### 修复前的错误日志

```
2026-02-11 09:40:55,013 - app.services.reply_generator_impl - WARNING - Failed to expand compact result: Invalid \escape: line 3 column 57 (char 67). Returning original result.
2026-02-11 09:40:55,014 - app.api.v1.predict - ERROR - Failed to parse reply text as JSON: ```json{"r": [["Okay, but promise you won't judge my silly posts! \[calm_presence, low_pressure_invite]", "calm_presence, low_pressure_invite"]
```

### 修复后的预期日志

```
2026-02-11 09:40:55,013 - app.api.v1.predict - INFO - Orchestrator response: ```json{"r": [["Okay, but promise you won't judge my silly posts! [calm_presence, low_pressure_invite]", "calm_presence, low_pressure_invite"]]}```
2026-02-11 09:40:55,014 - app.api.v1.predict - INFO - Reply generation successful: 3 replies
```

## 最佳实践

### 对于 LLM Prompt 工程

虽然我们在代码中修复了这个问题，但最好的做法是在 prompt 中明确指示 LLM 不要转义不需要转义的字符：

```
Return valid JSON. Do not escape brackets [], parentheses (), or braces {} inside strings.
Only escape characters that require escaping in JSON: " \ / b f n r t
```

### 对于其他 JSON 解析场景

如果在其他地方也需要解析 LLM 返回的 JSON，建议使用 `parse_json_with_markdown()` 函数，它包含了多种修复策略。

## 参考资料

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://datatracker.ietf.org/doc/html/rfc8259)
- [JSON.org: Introducing JSON](https://www.json.org/)
- [Python json module documentation](https://docs.python.org/3/library/json.html)

## 总结

通过在 JSON 修复流程中添加无效转义序列的处理，我们成功解决了 LLM 返回包含 `\[` 和 `\]` 等无效转义时的解析失败问题。这个修复：

1. ✅ 保留所有有效的 JSON 转义序列
2. ✅ 移除所有无效的转义序列
3. ✅ 完全向后兼容
4. ✅ 通过了全面的测试验证

修复后，系统能够正确解析包含策略标签（如 `[calm_presence, low_pressure_invite]`）的 LLM 响应。
