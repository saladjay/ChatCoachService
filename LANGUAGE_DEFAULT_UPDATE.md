# 语言默认值更新文档

## 概述

将系统的默认语言从中文（zh-CN）改为英语（en），以适应面向阿拉伯语、葡萄牙语、西班牙语和英语用户的需求。

## 修改内容

### 1. API 请求模型 (app/models/api.py)

**修改前：**
```python
language: str = Field(default="zh-CN", description="Language code")
```

**修改后：**
```python
language: str = Field(default="en", description="Language code (en/ar/pt/es/zh-CN)")
```

### 2. 内部数据模型 (app/models/schemas.py)

**修改前：**
```python
language: str = "zh-CN"  # 生成回复的语言（默认中文）
```

**修改后：**
```python
language: str = "en"  # 生成回复的语言（默认英语，支持 en/ar/pt/es 等）
```

### 3. 回复生成器 (app/services/reply_generator_impl.py)

**修改前：**
```python
# Get language from input (default to zh-CN if not provided)
language = getattr(input, 'language', 'zh-CN')
```

**修改后：**
```python
# Get language from input (must be provided, no default fallback)
# Language should always come from request to ensure consistency
language = input.language
```

**重要改进：**
- 移除了 `getattr` 的默认值回退
- 现在直接使用 `input.language`，确保语言始终来自请求
- 避免了在多个地方设置不同默认值的风险

### 4. API 文档 (interface.md)

**修改前：**
```markdown
| `language` | string | ❌ | `"zh-CN"` | 语言代码 |
```

**修改后：**
```markdown
| `language` | string | ❌ | `"en"` | 语言代码 (en/ar/pt/es/zh-CN) |
```

**示例请求更新：**
```json
{
  "language": "en"
}
```

### 5. 示例代码 (examples/api_client_example.py)

**修改前：**
```python
"language": "zh-CN",
```

**修改后：**
```python
"language": "en",  # Supports: en, ar, pt, es, zh-CN
```

### 6. 设计文档 (.kiro/specs/conversation-generation-service/design.md)

**修改前：**
```python
language: str = "zh-CN"
```

**修改后：**
```python
language: str = "en"  # Default to English (supports en/ar/pt/es/zh-CN)
```

### 7. 测试文件

#### test_api_validation_property.py

**修改前：**
```python
language_strategy = st.sampled_from(["zh-CN", "en-US", "ja-JP", "ko-KR"])
```

**修改后：**
```python
language_strategy = st.sampled_from(["en", "ar", "pt", "es", "zh-CN"])  # Supported languages
```

#### test_orchestrator_property.py

**修改前：**
```python
language="zh-CN",
```

**修改后：**
```python
language="en",  # Default to English
```

## 支持的语言

系统现在明确支持以下语言：

| 语言代码 | 语言名称 | 目标用户群 |
|---------|---------|-----------|
| `en` | English | 英语用户 |
| `ar` | العربية (Arabic) | 阿拉伯语用户 |
| `pt` | Português (Portuguese) | 葡萄牙语用户 |
| `es` | Español (Spanish) | 西班牙语用户 |
| `zh-CN` | 简体中文 (Simplified Chinese) | 中文用户 |

## 语言参数流转

确保语言参数在整个系统中保持一致：

```
GenerateReplyRequest (language="en")
    ↓
Orchestrator._generate_with_retry()
    ↓
ReplyGenerationInput (language="en")
    ↓
LLMAdapterReplyGenerator.generate_reply()
    ↓
CHATCOACH_PROMPT (language="en")
    ↓
LLM 生成英语回复
```

## 关键改进

1. **统一默认值**：所有地方的默认语言都改为 `"en"`
2. **明确支持的语言**：在文档和注释中明确列出支持的语言
3. **移除隐式回退**：在 reply_generator_impl.py 中移除了 `getattr` 的默认值，确保语言始终来自请求
4. **更新测试**：测试用例现在使用正确的语言列表

## 验证

所有修改已通过类型检查：
- ✅ app/models/api.py - No diagnostics found
- ✅ app/models/schemas.py - No diagnostics found
- ✅ app/services/reply_generator_impl.py - No diagnostics found

## 注意事项

1. **向后兼容性**：如果有现有客户端没有指定 `language` 参数，它们现在会默认获得英语回复而不是中文回复
2. **Prompt 语言**：CHATCOACH_PROMPT 本身使用中文编写，但会根据 `{language}` 参数生成指定语言的回复
3. **多语言 Prompt**：未来可能需要考虑为不同语言提供不同的 prompt 模板，以提高生成质量

## 相关文件

- `app/models/api.py` - API 请求模型
- `app/models/schemas.py` - 内部数据模型
- `app/services/reply_generator_impl.py` - 回复生成器
- `app/services/prompt.py` - Prompt 模板（已支持动态语言）
- `interface.md` - API 文档
- `examples/api_client_example.py` - 示例代码
- `.kiro/specs/conversation-generation-service/design.md` - 设计文档
- `tests/property/test_api_validation_property.py` - API 验证测试
- `tests/property/test_orchestrator_property.py` - Orchestrator 测试

## 更新日期

2024-01-19
