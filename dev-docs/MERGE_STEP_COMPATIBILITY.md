# Merge Step 兼容性验证报告

## 概述

本文档验证 `merge_step` prompt 的输出与现有数据结构的兼容性。

## 验证目标

确保 merge_step 的 JSON 输出可以转换为以下现有数据结构：

1. **ParsedScreenshotData** - 用于 `screenshot_parser` 服务
2. **ContextResult** - 用于 `context_builder` 服务  
3. **SceneAnalysisResult** - 用于 `scene_analyzer` 服务

## 数据结构映射

### 1. ParsedScreenshotData 映射

#### 源字段 (merge_step)
```json
{
  "screenshot_parse": {
    "participants": {
      "self": {"id":"user","nickname":"Alice"},
      "other": {"id":"talker","nickname":"Bob"}
    },
    "bubbles": [{
      "bubble_id":"1",
      "bbox":{"x1":10,"y1":20,"x2":200,"y2":80},
      "center_x":105,
      "center_y":50,
      "text":"Hey, how are you?",
      "sender":"user",
      "column":"left",
      "confidence":0.95
    }],
    "layout": {
      "type":"two_columns",
      "left_role":"user",
      "right_role":"talker"
    }
  }
}
```

#### 目标结构 (ParsedScreenshotData)
```python
ParsedScreenshotData(
    image_meta=ImageMeta(width=500, height=800),
    participants=Participants(
        self=Participant(id="user", nickname="Alice"),
        other=Participant(id="talker", nickname="Bob")
    ),
    bubbles=[ChatBubble(...)],
    layout=LayoutInfo(...)
)
```

✅ **完全兼容** - 所有字段都可以直接映射

### 2. ContextResult 映射

#### 源字段 (merge_step)
```json
{
  "conversation_analysis": {
    "conversation_summary":"Friendly greeting exchange",
    "emotion_state":"positive",
    "current_intimacy_level":60,
    "risk_flags":[]
  }
}
```

#### 目标结构 (ContextResult)
```python
ContextResult(
    conversation_summary="Friendly greeting exchange",
    emotion_state="positive",
    current_intimacy_level=60,
    risk_flags=[],
    conversation=[Message(...)],
    history_conversation=""
)
```

✅ **完全兼容** - 所有必需字段都存在
- `conversation` 字段从 dialogs 构建
- `history_conversation` 默认为空字符串

### 3. SceneAnalysisResult 映射

#### 源字段 (merge_step)
```json
{
  "scenario_decision": {
    "relationship_state":"推进",
    "scenario":"BALANCED",
    "intimacy_level":60,
    "risk_flags":[],
    "current_scenario":"friendly conversation",
    "recommended_scenario":"BALANCED",
    "recommended_strategies":["BE_SUPPORTIVE","SHOW_INTEREST","BE_FRIENDLY"]
  }
}
```

#### 目标结构 (SceneAnalysisResult)
```python
SceneAnalysisResult(
    relationship_state="推进",
    scenario="BALANCED",
    intimacy_level=60,
    risk_flags=[],
    current_scenario="friendly conversation",
    recommended_scenario="BALANCED",
    recommended_strategies=["BE_SUPPORTIVE","SHOW_INTEREST","BE_FRIENDLY"]
)
```

✅ **完全兼容** - 所有字段都可以直接映射

## 适配器实现

### MergeStepAdapter 类

位置: `app/services/merge_step_adapter.py`

提供三个主要方法：

1. **to_parsed_screenshot_data()** - 转换为 ParsedScreenshotData
2. **to_context_result()** - 转换为 ContextResult
3. **to_scene_analysis_result()** - 转换为 SceneAnalysisResult

### 便捷函数

```python
from app.services.merge_step_adapter import convert_merge_step_output

screenshot_data, context_result, scene_result = convert_merge_step_output(
    merge_output=llm_response,
    image_width=500,
    image_height=800,
    dialogs=dialogs
)
```

## 测试结果

运行 `python scripts/test_merge_step_adapter.py`:

```
✓ Output structure is valid
✓ Converting to ParsedScreenshotData - successful
✓ Converting to ContextResult - successful
✓ Converting to SceneAnalysisResult - successful
✓ All conversions successful via convenience function
✓ Invalid output correctly rejected
✓ All data types have required attributes
```

### 测试覆盖

- ✅ 结构验证
- ✅ ParsedScreenshotData 转换
- ✅ ContextResult 转换
- ✅ SceneAnalysisResult 转换
- ✅ 便捷函数
- ✅ 无效输入处理
- ✅ 数据类型兼容性

## Prompt 更新

原始 prompt 已更新以确保输出兼容性：

### 关键改进

1. **bbox 格式** - 从数组改为对象: `{"x1":0,"y1":0,"x2":0,"y2":0}`
2. **sender 值** - 从 "U"/"T" 改为 "user"/"talker"
3. **intimacy_level** - 从字符串改为 0-100 整数
4. **添加必需字段**:
   - `bubble_id`, `center_x`, `center_y`, `confidence`
   - `participants` 结构
   - `layout` 信息
   - `relationship_state`, `recommended_strategies`

## 向后兼容性

### 现有流程保持不变

✅ 所有现有数据类型保持不变：
- `ParseScreenshotRequest`
- `ParseScreenshotResponse`
- `GenerateReplyRequest`
- `GenerateReplyResponse`
- 所有内部数据模型

### 集成方式

merge_step 可以作为**可选优化**集成：

```python
# 方式 1: 使用现有分离流程（默认）
screenshot_data = await screenshot_parser.parse_screenshot(request)
context = await context_builder.build_context(input)
scene = await scene_analyzer.analyze_scene(input)

# 方式 2: 使用 merge_step 优化流程（新增）
merge_output = await llm_client.call_merge_step(prompt, image)
screenshot_data, context, scene = convert_merge_step_output(merge_output, ...)
```

## 性能对比

### 分离流程
- **LLM 调用**: 3 次
- **延迟**: ~3x
- **成本**: ~3x

### Merge 流程
- **LLM 调用**: 1 次
- **延迟**: ~1x
- **成本**: ~1x

**改进**: 约 66% 延迟和成本降低

## 使用示例

### 完整集成示例

```python
from app.services.merge_step_adapter import convert_merge_step_output
from app.services.llm_adapter import MultimodalLLMClient
from app.services.prompt_manager import get_prompt_manager, PromptType, PromptVersion

# 1. 获取 merge_step prompt
pm = get_prompt_manager()
prompt = pm.get_prompt_version(PromptType.MERGE_STEP, PromptVersion.V1_ORIGINAL)

# 2. 调用 LLM
llm_client = MultimodalLLMClient()
llm_response = await llm_client.call(prompt=prompt, image_base64=image_data)

# 3. 转换输出
screenshot_data, context_result, scene_result = convert_merge_step_output(
    merge_output=llm_response.parsed_json,
    image_width=image_width,
    image_height=image_height,
    dialogs=dialogs
)

# 4. 使用转换后的数据（与现有流程完全相同）
# screenshot_data 可用于 ParseScreenshotResponse
# context_result 可用于后续处理
# scene_result 可用于场景分析
```

## 验证清单

- ✅ Prompt 输出格式与现有数据结构兼容
- ✅ 适配器可以正确转换所有字段
- ✅ 所有必需字段都存在
- ✅ 数据类型正确（int, str, list, etc.）
- ✅ 向后兼容性保持
- ✅ 测试覆盖完整
- ✅ 文档完整

## 结论

✅ **merge_step prompt 的输出完全兼容现有数据结构**

通过 `MergeStepAdapter`，merge_step 的输出可以无缝转换为：
- ParsedScreenshotData (screenshot_parser)
- ContextResult (context_builder)
- SceneAnalysisResult (scene_analyzer)

这意味着 merge_step 可以作为现有流程的**直接替代**，无需修改任何下游代码。

## 相关文件

- Prompt: `prompts/versions/merge_step_v1.0-original.txt`
- 适配器: `app/services/merge_step_adapter.py`
- 测试: `scripts/test_merge_step_adapter.py`
- 数据模型: `app/models/screenshot.py`, `app/models/schemas.py`
