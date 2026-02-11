# JSON Parsing Improvements

## 概述

本文档描述了对 LLM JSON 响应解析逻辑的改进，以及失败响应的记录机制。

## 问题背景

### 原始问题

在 `merge_step_analysis` 过程中，LLM 可能返回：
1. 不完整的 JSON（被截断）
2. 格式错误的 JSON（缺少闭合括号）
3. 包含非 JSON 内容的响应

原有的解析逻辑使用简单的正则表达式 `r"\{.*\}"` 进行贪婪匹配，可能会：
- 匹配到不完整的 JSON 片段
- 无法正确处理字符串中的括号
- 难以提取多个 JSON 对象

### 错误示例

```
ValueError: Could not extract valid JSON from response: ```json{"screenshot_parse": {"participants": {"self": {"id": "user","nickname": "..."},"other": {"id": "talker","nickname": "ddddddyj"...
```

## 解决方案

### 1. 改进的 JSON 提取逻辑

#### 新增：栈匹配算法

实现了 `_extract_complete_json_objects()` 方法，使用栈来匹配括号：

```python
def _extract_complete_json_objects(self, text: str) -> list[str]:
    """使用栈匹配提取完整的 JSON 对象"""
    results = []
    stack = []
    start_idx = None
    in_string = False
    escape_next = False
    
    for i, char in enumerate(text):
        # 处理转义字符
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        # 跟踪是否在字符串内（忽略字符串中的括号）
        if char == '"':
            in_string = not in_string
            continue
        
        # 只处理字符串外的括号
        if not in_string:
            if char == '{':
                if not stack:
                    start_idx = i
                stack.append('{')
            elif char == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
                    if not stack and start_idx is not None:
                        # 找到完整的 JSON 对象
                        results.append(text[start_idx:i+1])
                        start_idx = None
    
    return results
```

#### 特性

- **正确处理字符串中的括号**：`{"msg": "This has { and } in it"}`
- **正确处理转义引号**：`{"msg": "He said \"hello\""}`
- **提取多个 JSON 对象**：可以从文本中提取多个独立的 JSON
- **检测不完整的 JSON**：如果括号不匹配，返回空列表

#### 解析顺序（Fallback 模式）

`_parse_json_response()` 方法按以下顺序尝试解析：

1. **直接 JSON 解析**：`json.loads(raw_text)`
2. **Markdown 代码块提取**：从 ````json ... ``` 中提取
3. **栈匹配算法**（新增）：使用 `_extract_complete_json_objects()`
4. **简单正则表达式**（保留）：使用 `r"\{.*\}"` 作为最后的 fallback

### 2. 失败响应记录机制

#### 新增：`_save_failed_response()` 方法

当所有解析尝试都失败时，自动保存完整的原始响应：

```python
def _save_failed_response(self, raw_text: str, error: str) -> None:
    """保存解析失败的响应到文件用于调试"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    failed_dir = Path("failed_json_replies")
    failed_dir.mkdir(exist_ok=True)
    
    filename = f"failed_reply_{timestamp}_multimodal.json"
    filepath = failed_dir / filename
    
    data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "error": error,
        "raw_text": raw_text,  # 完整的原始文本
        "raw_text_length": len(raw_text),
        "truncated_preview": raw_text[:500],  # 前 500 字符预览
        "source": "multimodal_llm_client",
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
```

#### 保存的信息

- `timestamp`：失败时间（ISO 格式）
- `error`：错误描述
- `raw_text`：**完整的原始响应**（这是关键！）
- `raw_text_length`：响应长度
- `truncated_preview`：前 500 字符预览
- `source`：来源标识（`multimodal_llm_client`）

#### 文件位置

失败的响应保存在：
```
failed_json_replies/failed_reply_<timestamp>_multimodal.json
```

### 3. 增强的错误日志

#### Orchestrator 层面

在 `app/services/orchestrator.py` 的 `merge_step_analysis()` 中：

```python
try:
    llm_response = await llm_client.call(
        prompt=prompt,
        image_base64=image_base64,
    )
except RuntimeError as e:
    error_msg = str(e)
    # 增强的 JSON 解析失败日志
    if "Failed to parse JSON" in error_msg:
        logger.error(
            f"JSON parsing failed in merge_step analysis. "
            f"The LLM returned invalid or incomplete JSON. "
            f"Details: {error_msg}. "
            f"Check the 'failed_json_replies/' directory for the complete raw response. "
            f"This may indicate: 1) LLM output was truncated, "
            f"2) LLM returned non-JSON text, or 3) JSON structure is malformed."
        )
    raise
```

#### LLM Adapter 层面

在 `app/services/llm_adapter.py` 的 `_save_failed_response()` 中：

```python
logger.warning(
    f"Failed JSON response saved to {filepath}. "
    f"Response length: {len(raw_text)} chars. "
    f"Review this file to understand why JSON parsing failed."
)
```

## 测试

### 测试脚本

创建了 `scripts/test_json_extraction_standalone.py` 来验证新的提取逻辑。

### 测试用例

- ✓ 简单 JSON
- ✓ 嵌套对象
- ✓ 字符串中包含括号
- ✓ 多个 JSON 对象
- ✓ Markdown 代码块中的 JSON
- ✓ 不完整的 JSON（截断）
- ✓ 转义引号
- ✓ 真实错误案例

运行测试：
```bash
python scripts/test_json_extraction_standalone.py
```

## 使用指南

### 调试 JSON 解析错误

1. **查看日志**：
   ```
   ERROR - JSON parsing failed in merge_step analysis.
   Check the 'failed_json_replies/' directory for the complete raw response.
   ```

2. **找到失败的响应文件**：
   ```bash
   ls -lt failed_json_replies/
   # 查看最新的 failed_reply_*_multimodal.json 文件
   ```

3. **分析原始响应**：
   ```json
   {
     "timestamp": "2026-02-05T13:22:14.579083",
     "error": "Could not extract valid JSON from response",
     "raw_text": "完整的 LLM 响应...",
     "raw_text_length": 1234,
     "truncated_preview": "前 500 字符...",
     "source": "multimodal_llm_client"
   }
   ```

4. **确定问题类型**：
   - **截断**：`raw_text` 末尾不完整（缺少闭合括号）
   - **非 JSON**：LLM 返回了自然语言而非 JSON
   - **格式错误**：JSON 结构有语法错误

5. **采取行动**：
   - 调整 prompt 以强调 JSON 格式要求
   - 增加 `max_tokens` 限制以避免截断
   - 检查 LLM 配置和模型选择

## 优势

### 相比原有方案

1. **更准确的提取**：栈匹配算法能正确处理嵌套和字符串中的括号
2. **完整的调试信息**：保存完整的原始响应，而不仅仅是前 200 字符
3. **保留兼容性**：使用 fallback 模式，保留原有的正则表达式逻辑
4. **详细的错误日志**：在多个层面提供清晰的错误信息

### 对生产环境的影响

- **零破坏性**：完全向后兼容，不影响现有功能
- **自动记录**：无需手动干预，自动保存失败响应
- **易于调试**：提供完整信息，快速定位问题

## 相关文件

- `app/services/llm_adapter.py`：JSON 解析和失败记录逻辑
- `app/services/orchestrator.py`：增强的错误日志
- `scripts/test_json_extraction_standalone.py`：测试脚本
- `failed_json_replies/`：失败响应保存目录

## 未来改进

1. **统计分析**：定期分析 `failed_json_replies/` 中的失败模式
2. **自动修复**：对常见的格式错误尝试自动修复
3. **Prompt 优化**：根据失败模式优化 prompt 模板
4. **监控告警**：当失败率超过阈值时发送告警

## 更新日期

2026-02-05
