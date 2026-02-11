# Merge Step Conversation Logging

## 概述

为了更好地调试和监控 merge_step 对话提取过程，系统现在会在 INFO 级别打印详细的对话信息。

## 日志格式

### 1. 参与者信息
```
INFO - [session_id] merge_step [strategy|model] Participants: User='昵称1', Target='昵称2'
```

### 2. 对话消息列表
```
INFO - [session_id] merge_step [strategy|model] Extracted N messages:
INFO - [session_id]   [1] speaker (position): 消息内容
INFO - [session_id]   [2] speaker (position): 消息内容
...
```

## 示例输出

```
2026-02-09 08:15:17,045 - app.services.screenshot_parser - INFO - [load_test_session_123] merge_step [premium|google/gemini-2.0-flash-001] Participants: User='小明', Target='小红'
2026-02-09 08:15:17,046 - app.services.screenshot_parser - INFO - [load_test_session_123] merge_step [premium|google/gemini-2.0-flash-001] Extracted 5 messages:
2026-02-09 08:15:17,047 - app.services.screenshot_parser - INFO - [load_test_session_123]   [1] user (left): 你好，最近怎么样？
2026-02-09 08:15:17,048 - app.services.screenshot_parser - INFO - [load_test_session_123]   [2] target (right): 挺好的，谢谢！你呢？
2026-02-09 08:15:17,049 - app.services.screenshot_parser - INFO - [load_test_session_123]   [3] user (left): 也不错，刚完成一个大项目
2026-02-09 08:15:17,050 - app.services.screenshot_parser - INFO - [load_test_session_123]   [4] target (right): 太棒了！恭喜！🎉
2026-02-09 08:15:17,051 - app.services.screenshot_parser - INFO - [load_test_session_123]   [5] user (left): 谢谢！要不要一起吃饭庆祝？
```

## 日志包含的信息

- ✅ **Session ID**: 会话标识符
- ✅ **Strategy**: 使用的策略（multimodal 或 premium）
- ✅ **Model**: 实际使用的模型名称
- ✅ **Participants**: 对话双方的昵称
- ✅ **Message Count**: 提取的消息数量
- ✅ **Speaker**: 说话者（user/target）
- ✅ **Position**: 消息位置（left/right）
- ✅ **Content**: 消息内容（超过100字符会截断）

## 触发时机

日志会在以下情况自动打印：

1. **merge_step 分析**: 当任一模型（multimodal 或 premium）成功提取对话时
2. **screenshot_parse**: 当截图解析成功提取对话时

## 竞速策略

系统同时调用两个模型：
- **multimodal**: 快速模型（如 mistralai/ministral-3b-2512）
- **premium**: 高质量模型（如 google/gemini-2.0-flash-001）

哪个先返回有效结果就使用哪个，并打印该模型的日志。

## 移除的旧日志

以下旧的日志格式已被移除（不易阅读）：

```
# 旧格式（已移除）
INFO - Dialog: [DialogItem(position=[0.0, 0.0, 0.0, 0.0], text='...', speaker='talker', from_user=False), ...]
INFO - conversation:[{'speaker': 'talker', 'text': '...'}, {'speaker': 'user', 'text': '...'}, ...]
```

## 实现位置

- **merge_step 日志方法**: `app/services/orchestrator.py`
  - `_log_merge_step_extraction()`: 在 orchestrator 中打印 merge_step 提取的对话
- **screenshot_parse 日志方法**: `app/services/screenshot_parser.py`
  - `_log_merge_step_conversation()`: 在 race 策略中打印（已集成但未使用）
  - `_log_screenshot_dialogs()`: 打印 screenshot_parse 提取的对话
- **触发位置**: 
  - merge_step: `orchestrator.py` 的 `merge_step_analysis()` 方法中，JSON 解析成功后
  - screenshot_parse: `screenshot_parser.py` 的 `_race_multimodal_calls()` 方法中，验证成功后
- **移除位置**: `app/api/v1/predict.py` 中的旧日志已移除

## 数据结构

### merge_step JSON 结构
```json
{
  "screenshot_parse": {
    "participants": {
      "user": {"nickname": "昵称1"},
      "target": {"nickname": "昵称2"}
    },
    "bubbles": [...]
  },
  "conversation_analysis": {
    "conversation": [
      {"speaker": "user", "content": "消息内容", "position": "left"},
      {"speaker": "target", "content": "消息内容", "position": "right"}
    ],
    "conversation_summary": "...",
    "emotion_state": "...",
    "current_intimacy_level": 50
  },
  "scenario_decision": {
    "relationship_state": "...",
    "recommended_scenario": "..."
  }
}
```

日志从 `conversation_analysis.conversation` 和 `screenshot_parse.participants` 中提取信息。

## 配置

无需额外配置，日志级别为 INFO，默认启用。

如需禁用，可以在日志配置中调整 `app.services.screenshot_parser` 的日志级别。
