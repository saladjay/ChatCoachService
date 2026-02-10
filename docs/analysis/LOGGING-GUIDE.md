# Last Message 日志输出指南

## 概述

本文档说明 Last Message 选择过程中的日志输出格式，帮助调试和验证功能。

---

## 日志级别

所有 Last Message 相关的日志都使用 `INFO` 级别，确保在生产环境中可见。

---

## 日志输出位置

### 1. `app/api/v1/predict.py` - `_generate_reply` 函数

**位置**: Reply generation 开始时

**日志格式**:
```
============================================================
Reply generation requested, calling Orchestrator
Last content type: text
Last content value: 这是最后一段文字...
============================================================
```

**说明**:
- 显示最后一个 content 的类型（`text` 或 `image`）
- 显示最后一个 content 的值（文字内容或图片 URL）

---

### 2. `app/api/v1/predict.py` - Reply Sentence 选择逻辑

**位置**: 在最后一个 analysis_queue 元素处理时

#### 场景 A: 最后是文字

**日志格式**:
```
------------------------------------------------------------
Selecting reply_sentence (Last Message):
  - Last content type: text
  - Strategy: Using text content directly
  - Reply sentence: '这是最后一段文字'
------------------------------------------------------------
```

#### 场景 B: 最后是图片

**日志格式**:
```
------------------------------------------------------------
Selecting reply_sentence (Last Message):
  - Last content type: image
  - Strategy: Finding talker/left message from image
  - Found last image: https://example.com/chat.jpg
  - Searching in 4 dialogs from last image
  - Reply sentence: '在工作呢'
------------------------------------------------------------
```

#### 场景 C: 图片（后备方案）

**日志格式**:
```
------------------------------------------------------------
Selecting reply_sentence (Last Message):
  - Last content type: image
  - Strategy: Finding talker/left message from image
  - No image result found, using all dialogs (fallback)
  - Searching in 4 dialogs
  - Reply sentence: '在工作呢'
------------------------------------------------------------
```

---

### 3. `app/api/v1/predict.py` - `_find_last_talker_message` 函数

**位置**: 查找 talker/left 消息时

#### 成功找到

**日志格式**:
```
Found talker/left message: 在工作呢...
```

#### 没有找到（抛出异常）

**日志格式**:
```
No talker/left message found in dialogs
```

---

### 4. `app/api/v1/predict.py` - 传递给 Orchestrator

**位置**: 创建 GenerateReplyRequest 后

**日志格式**:
```
Passing reply_sentence to orchestrator: '在工作呢'
```

---

### 5. `app/services/prompt_assembler.py` - PromptAssembler

**位置**: 组装 prompt 时

**日志格式**:
```
============================================================
PromptAssembler: Determining reply_sentence (Last Message)
  - Input reply_sentence: '在工作呢'
  - Final reply_sentence (Last Message): '在工作呢'
============================================================
```

**或者（如果 input 为空）**:
```
============================================================
PromptAssembler: Determining reply_sentence (Last Message)
  - Input reply_sentence: ''
  - Input reply_sentence is empty, inferring from conversation
  - Explicit reply_sentence from request: '在工作呢'
  - Final reply_sentence (Last Message): '在工作呢'
============================================================
```

---

### 6. `app/services/prompt_assembler.py` - `_infer_reply_sentence` 方法

**位置**: 推断 reply_sentence 时

#### 使用 explicit reply_sentence

**日志格式**:
```
  _infer_reply_sentence called:
    - Explicit reply_sentence provided: True
    - Using explicit reply_sentence: '在工作呢'
```

#### 从对话中推断

**日志格式**:
```
  _infer_reply_sentence called:
    - Explicit reply_sentence provided: False
    - No explicit reply_sentence, inferring from 4 messages
    - Found non-user message (speaker='talker'): '在工作呢'
```

#### 后备方案

**日志格式**:
```
  _infer_reply_sentence called:
    - Explicit reply_sentence provided: False
    - No explicit reply_sentence, inferring from 4 messages
    - Fallback: using last message: '在工作呢'
```

#### 没有找到

**日志格式**:
```
  _infer_reply_sentence called:
    - Explicit reply_sentence provided: False
    - No explicit reply_sentence, inferring from 0 messages
    - No messages available, returning empty string
```

---

## 完整的日志流程示例

### 示例 1: 纯文字场景

```
============================================================
Reply generation requested, calling Orchestrator
Last content type: text
Last content value: 这是最后一段文字
============================================================
------------------------------------------------------------
Selecting reply_sentence (Last Message):
  - Last content type: text
  - Strategy: Using text content directly
  - Reply sentence: '这是最后一段文字'
------------------------------------------------------------
Passing reply_sentence to orchestrator: '这是最后一段文字'
============================================================
PromptAssembler: Determining reply_sentence (Last Message)
  - Input reply_sentence: '这是最后一段文字'
  - Final reply_sentence (Last Message): '这是最后一段文字'
============================================================
```

### 示例 2: 纯图片场景

```
============================================================
Reply generation requested, calling Orchestrator
Last content type: image
Last content value: https://example.com/chat.jpg...
============================================================
------------------------------------------------------------
Selecting reply_sentence (Last Message):
  - Last content type: image
  - Strategy: Finding talker/left message from image
  - Found last image: https://example.com/chat.jpg
  - Searching in 4 dialogs from last image
------------------------------------------------------------
Found talker/left message: 在工作呢...
------------------------------------------------------------
  - Reply sentence: '在工作呢'
------------------------------------------------------------
Passing reply_sentence to orchestrator: '在工作呢'
============================================================
PromptAssembler: Determining reply_sentence (Last Message)
  - Input reply_sentence: '在工作呢'
  - Final reply_sentence (Last Message): '在工作呢'
============================================================
```

### 示例 3: 混合场景 - 最后是文字

```
============================================================
Reply generation requested, calling Orchestrator
Last content type: text
Last content value: 这是最后一段文字
============================================================
------------------------------------------------------------
Selecting reply_sentence (Last Message):
  - Last content type: text
  - Strategy: Using text content directly
  - Reply sentence: '这是最后一段文字'
------------------------------------------------------------
Passing reply_sentence to orchestrator: '这是最后一段文字'
============================================================
PromptAssembler: Determining reply_sentence (Last Message)
  - Input reply_sentence: '这是最后一段文字'
  - Final reply_sentence (Last Message): '这是最后一段文字'
============================================================
```

### 示例 4: 错误场景 - 图片中没有 talker

```
============================================================
Reply generation requested, calling Orchestrator
Last content type: image
Last content value: https://example.com/only_user.jpg...
============================================================
------------------------------------------------------------
Selecting reply_sentence (Last Message):
  - Last content type: image
  - Strategy: Finding talker/left message from image
  - Found last image: https://example.com/only_user.jpg
  - Searching in 3 dialogs from last image
------------------------------------------------------------
No talker/left message found in dialogs
[HTTPException 400: No talker message found in the image...]
```

---

## 日志搜索关键词

在日志中搜索以下关键词可以快速定位 Last Message 相关的信息：

| 关键词 | 说明 |
|--------|------|
| `Reply generation requested` | Reply generation 开始 |
| `Last content type` | 最后一个 content 的类型 |
| `Selecting reply_sentence` | Reply sentence 选择开始 |
| `Reply sentence:` | 最终选择的 reply sentence |
| `Found talker/left message` | 找到 talker/left 消息 |
| `No talker/left message found` | 没有找到 talker/left 消息 |
| `Passing reply_sentence to orchestrator` | 传递给 orchestrator |
| `PromptAssembler: Determining reply_sentence` | PromptAssembler 处理 |
| `Final reply_sentence (Last Message)` | 最终的 Last Message |

---

## 调试建议

### 1. 验证 Last Message 选择

搜索日志中的 `Reply sentence:` 和 `Final reply_sentence`，确认它们是否符合预期。

### 2. 检查类型判断

搜索 `Last content type:`，确认系统正确识别了最后一个 content 的类型。

### 3. 追踪数据流

按顺序查看以下日志：
1. `Reply generation requested` - 输入
2. `Selecting reply_sentence` - 选择过程
3. `Passing reply_sentence to orchestrator` - 传递
4. `PromptAssembler: Determining reply_sentence` - 最终使用

### 4. 排查错误

如果看到 `No talker/left message found`，说明图片中没有 talker/left 的消息，系统会抛出 400 错误。

---

## 日志级别配置

确保日志级别设置为 `INFO` 或更低（如 `DEBUG`），否则这些日志不会显示。

**配置文件**: `.env` 或环境变量

```bash
LOG_LEVEL=INFO
```

---

## 相关文档

- **测试结果**: [TEST-RESULTS.md](./TEST-RESULTS.md)
- **实施完成总结**: [IMPLEMENTATION-COMPLETE.md](./IMPLEMENTATION-COMPLETE.md)
- **快速参考**: [QUICK-REFERENCE.md](./QUICK-REFERENCE.md)
