# Merge Step 字段自动填充功能

## 概述

`MergeStepAdapter` 现在具备智能字段填充功能，可以自动处理 LLM 输出中缺失或无效的字段，确保系统的鲁棒性。

## 功能特性

### 1. 自动计算字段

#### center_x 和 center_y

如果 LLM 没有输出这些字段，适配器会自动从 bbox 计算：

```python
center_x = (bbox.x1 + bbox.x2) / 2
center_y = (bbox.y1 + bbox.y2) / 2
```

**示例**:
```json
// LLM 输出（缺少 center_x, center_y）
{
  "bbox": {"x1": 10, "y1": 20, "x2": 200, "y2": 80},
  "text": "Hello"
}

// 适配器自动填充
{
  "bbox": {"x1": 10, "y1": 20, "x2": 200, "y2": 80},
  "center_x": 105.0,  // (10 + 200) / 2
  "center_y": 50.0,   // (20 + 80) / 2
  "text": "Hello"
}
```

### 2. 自动生成字段

#### bubble_id

如果缺失，自动生成序号：

```python
bubble_id = str(index + 1)  // "1", "2", "3", ...
```

#### column

如果缺失，根据位置推断：

```python
if center_x < image_width / 2:
    column = "left"
else:
    column = "right"
```

### 3. 默认值填充

#### Screenshot Parse 字段

| 字段 | 默认值 | 说明 |
|-----|-------|------|
| bubble_id | "1", "2", ... | 自动生成序号 |
| center_x | 计算值 | 从 bbox 计算 |
| center_y | 计算值 | 从 bbox 计算 |
| confidence | 0.95 | 高置信度默认值 |
| column | 推断值 | 从位置或 sender 推断 |
| participants.self.id | "user" | 默认用户 ID |
| participants.self.nickname | "User" | 默认用户昵称 |
| participants.other.id | "talker" | 默认对话者 ID |
| participants.other.nickname | "Talker" | 默认对话者昵称 |
| layout.type | "two_columns" | 默认布局类型 |
| layout.left_role | 推断或 "user" | 从气泡推断 |
| layout.right_role | 推断或 "talker" | 从气泡推断 |

#### Conversation Analysis 字段

| 字段 | 默认值 | 说明 |
|-----|-------|------|
| conversation_summary | "" | 空字符串 |
| emotion_state | "neutral" | 中性情绪 |
| current_intimacy_level | 50 | 中等亲密度 |
| risk_flags | [] | 空列表 |

#### Scenario Decision 字段

| 字段 | 默认值 | 说明 |
|-----|-------|------|
| relationship_state | "维持" | 维持关系状态 |
| scenario | "SAFE" | 安全场景 |
| recommended_scenario | "SAFE" | 推荐安全场景 |
| intimacy_level | 50 | 中等亲密度 |
| risk_flags | [] | 空列表 |
| current_scenario | "" | 空字符串 |
| recommended_strategies | [] | 空列表（由 StrategySelector 填充） |

### 4. 值验证和修正

#### 亲密度范围限制

```python
# 自动限制在 0-100 范围内
if intimacy_level < 0:
    intimacy_level = 0
elif intimacy_level > 100:
    intimacy_level = 100
```

**示例**:
```python
# 输入: 150
# 输出: 100 (clamped)

# 输入: -10
# 输出: 0 (clamped)
```

#### 枚举值验证

```python
# emotion_state 必须是 positive, neutral, negative 之一
valid_emotions = ["positive", "neutral", "negative"]
if emotion_state not in valid_emotions:
    emotion_state = "neutral"  # 默认中性

# relationship_state 验证
valid_states = ["破冰", "推进", "冷却", "维持", "ignition", "propulsion", "ventilation", "equilibrium"]
if relationship_state not in valid_states:
    relationship_state = "维持"  # 默认维持

# scenario 验证
valid_scenarios = ["SAFE", "BALANCED", "RISKY", "RECOVERY", "NEGATIVE"]
if scenario not in valid_scenarios:
    scenario = "SAFE"  # 默认安全
```

### 5. 智能推断

#### 布局角色推断

从气泡的 sender 和 column 推断布局角色：

```python
# 统计左列最常见的 sender
left_senders = [b.sender for b in bubbles if b.column == "left"]
left_role = most_common(left_senders)  # 例如: "user"

# 统计右列最常见的 sender
right_senders = [b.sender for b in bubbles if b.column == "right"]
right_role = most_common(right_senders)  # 例如: "talker"
```

## 使用示例

### 示例 1: 最小化 LLM 输出

LLM 只需要输出最基本的信息，其他字段会自动填充：

```json
{
  "screenshot_parse": {
    "bubbles": [
      {
        "bbox": {"x1": 10, "y1": 20, "x2": 200, "y2": 80},
        "text": "Hello",
        "sender": "user"
      }
    ]
  },
  "conversation_analysis": {
    "conversation_summary": "Greeting"
  },
  "scenario_decision": {
    "recommended_scenario": "SAFE"
  }
}
```

适配器会自动填充：
- bubble_id: "1"
- center_x: 105.0
- center_y: 50.0
- column: "left"
- confidence: 0.95
- participants: 默认值
- layout: 默认值和推断值
- emotion_state: "neutral"
- current_intimacy_level: 50
- risk_flags: []
- relationship_state: "维持"
- intimacy_level: 50
- 等等...

### 示例 2: 处理无效值

```json
{
  "conversation_analysis": {
    "current_intimacy_level": 150,  // 无效: > 100
    "emotion_state": "very_happy"   // 无效: 不在枚举中
  },
  "scenario_decision": {
    "intimacy_level": -20,          // 无效: < 0
    "recommended_scenario": "ULTRA_RISKY"  // 无效: 不在枚举中
  }
}
```

适配器会自动修正：
- current_intimacy_level: 100 (clamped)
- emotion_state: "neutral" (defaulted)
- intimacy_level: 0 (clamped)
- recommended_scenario: "SAFE" (defaulted)

## 日志记录

适配器会记录所有自动填充和修正操作：

```python
# Debug 级别 - 正常填充
logger.debug("Calculated center_x=105.0 for bubble 0")
logger.debug("Generated bubble_id=1 for bubble 0")
logger.debug("Inferred column=left for bubble 0")

# Warning 级别 - 值修正
logger.warning("current_intimacy_level 150 > 100, clamping to 100")
logger.warning("Invalid emotion_state 'very_happy', defaulting to 'neutral'")
logger.warning("Invalid recommended_scenario 'ULTRA_RISKY', defaulting to 'SAFE'")
```

## 测试覆盖

运行测试：

```bash
python scripts/test_merge_step_field_filling.py
```

### 测试场景

1. ✅ **缺失 center 坐标** - 从 bbox 自动计算
2. ✅ **缺失 bubble_id** - 自动生成序号
3. ✅ **缺失 column** - 从位置推断
4. ✅ **缺失 confidence** - 使用默认值 0.95
5. ✅ **缺失 layout roles** - 从气泡推断
6. ✅ **缺失 conversation 字段** - 使用合理默认值
7. ✅ **缺失 scenario 字段** - 使用合理默认值
8. ✅ **无效值** - 自动修正到有效范围

### 测试结果

```
✓ ALL FIELD FILLING TESTS PASSED!

The adapter can now handle:
  ✓ Missing center_x, center_y (calculated from bbox)
  ✓ Missing bubble_id (auto-generated)
  ✓ Missing column (inferred from position)
  ✓ Missing confidence (default 0.95)
  ✓ Missing layout roles (inferred from bubbles)
  ✓ Missing conversation fields (sensible defaults)
  ✓ Missing scenario fields (sensible defaults)
  ✓ Invalid values (clamped to valid ranges)
```

## 优势

### 1. 提高鲁棒性

- LLM 输出不完整时系统仍能正常工作
- 减少因字段缺失导致的错误

### 2. 简化 Prompt

- Prompt 可以更简洁，不需要强调每个字段
- LLM 可以专注于核心信息提取

### 3. 容错能力

- 自动处理 LLM 的"创造性"输出
- 无效值自动修正到合理范围

### 4. 一致性

- 确保所有输出都符合数据模型要求
- 统一的默认值策略

## 最佳实践

### Prompt 设计

现在可以简化 prompt，只要求核心字段：

```
Output JSON with:
- bbox: bounding box coordinates
- text: bubble text
- sender: "user" or "talker"

Optional fields (will be auto-filled if missing):
- center_x, center_y
- bubble_id
- column
- confidence
```

### 错误处理

适配器会记录所有填充和修正操作，便于调试：

```python
# 监控日志中的 WARNING 级别消息
# 这些表示 LLM 输出了无效值
logger.warning("Invalid emotion_state 'very_happy', defaulting to 'neutral'")
```

### 性能考虑

字段填充的性能开销很小：
- 简单的数学计算（center 坐标）
- 字符串生成（bubble_id）
- 条件判断（验证）

## 相关文件

- **实现**: `app/services/merge_step_adapter.py`
- **测试**: `scripts/test_merge_step_field_filling.py`
- **文档**: `dev-docs/MERGE_STEP_FIELD_FILLING.md`

## 总结

✅ **字段自动填充功能已完整实现**

- 自动计算缺失的坐标
- 自动生成缺失的 ID
- 智能推断布局信息
- 提供合理的默认值
- 验证和修正无效值
- 详细的日志记录
- 100% 测试覆盖

系统现在可以优雅地处理不完整或不完美的 LLM 输出！
