# Last Message 修改方案

## 问题概述

当前 `reply_sentence` (Last Message) 的选择逻辑不符合用户期望：

**用户期望**：
1. 如果最后一个 content 是**图片** → Last Message 应该是 dialog 中属于 **talker left** 的最后一句话
2. 如果最后一个 content 是**文字** → Last Message 应该是 **content 文字本身**

**当前问题**：
- 没有区分最后一个 content 的类型（图片 vs 文字）
- "talker left" 的识别不准确（当前只检查 `speaker not in user_speakers`）
- 将所有 content 的 dialogs 合并后统一处理，丢失了最后一个 content 的类型信息

## 数据流分析

### 1. Content 处理 (`app/api/v1/predict.py`)

```python
# 第 1062-1250 行
items: list[tuple[Literal["image", "text"], str, ImageResult]] = []
for content_url in request.content:
    if not _is_url(content_url):
        # 文字内容
        text_result = ImageResult(
            content=content_url,
            dialogs=[DialogItem(
                position=[0.0, 0.0, 0.0, 0.0],
                text=content_url,  # 文字直接作为 text
                speaker="",        # 空字符串
                from_user=False,
            )]
        )
        items.append(("text", content_url, text_result))
    else:
        # 图片 URL - 通过 LLM 解析
        image_result = await get_merge_step_analysis_result(...)
        items.append(("image", content_url, image_result))
```

**关键信息**：
- `items` 列表保留了每个 content 的类型（"image" 或 "text"）
- 文字 content 的 `speaker` 为空字符串 `""`
- 图片 content 的 `speaker` 由 LLM 解析得出（如 "user", "talker"）

### 2. Analysis Queue 构建 (`app/api/v1/predict.py`)

```python
# 第 1380-1420 行
analysis_queue: List[ImageAnalysisQueueInput] = []
for kind, item_key, item_result in items:
    if kind == "image":
        # 遇到图片时，结束当前组，开始新组
        if current_content_keys or current_dialogs or current_ImageResultList:
            analysis_queue.append((
                deepcopy(current_content_keys),
                deepcopy(current_dialogs),
                deepcopy(current_ImageResultList),
            ))
            current_content_keys = []
            current_dialogs = []
            current_ImageResultList = []
        
        current_dialogs = current_dialogs + item_result.dialogs
        current_ImageResultList.append(item_result)
        current_content_keys.append(item_key)
    else:
        # 文字内容累积到当前组
        current_dialogs = current_dialogs + item_result.dialogs
        current_ImageResultList.append(item_result)
        current_content_keys.append(item_key)
```

**关键信息**：
- `analysis_queue` 是一个列表，每个元素是一个组：`(resources, dialogs, image_results)`
- 图片会触发分组，文字会累积到当前组
- **问题**：分组后丢失了最后一个 content 的类型信息

### 3. Reply Generation (`app/api/v1/predict.py`)

```python
# 第 1000-1005 行
for resource_index, (resources, dialog, list_image_result) in enumerate(analysis_queue):
    conversation = []
    for dialog_item in dialog:
        conversation.append({
            "speaker": dialog_item.speaker,
            "text": dialog_item.text,
        })
    
    orchestrator_request = GenerateReplyRequest(
        user_id=request.user_id,
        target_id="unknown",
        conversation_id=request.session_id,
        resources=resources,
        dialogs=conversation,  # 传递给 orchestrator
        language=request.language,
        quality="normal",
        persona=request.other_properties.lower(),
        scene=request.scene,
    )
    
    if resource_index < len(analysis_queue) - 1:
        await orchestrator.prepare_generate_reply(orchestrator_request)
        continue
    
    orchestrator_response = await orchestrator.generate_reply(orchestrator_request)
```

**关键信息**：
- 只有最后一个 analysis_queue 元素会调用 `generate_reply`
- 前面的元素只调用 `prepare_generate_reply`（准备上下文和场景）
- `dialogs` 传递给 orchestrator，但没有传递最后一个 content 的类型信息

### 4. Orchestrator 处理 (`app/services/orchestrator.py`)

```python
# 第 1265-1400 行
async def _generate_with_retry(
    self,
    exec_ctx: ExecutionContext,
    request: GenerateReplyRequest,
    context: ContextResult,
    scene: SceneAnalysisResult,
    persona: PersonaSnapshot,
    strategy_plan=None,
):
    # ...
    reply_input = ReplyGenerationInput(
        user_id=request.user_id,
        prompt=f"Generate a reply for conversation {request.conversation_id}",
        quality=quality,
        context=context,  # context.conversation 包含对话历史
        scene=scene,
        persona=persona,
        language=request.language,
    )
    reply_result = await self._execute_step(
        exec_ctx,
        f"reply_generation_attempt_{attempt + 1}",
        self.reply_generator.generate_reply,
        reply_input,
    )
```

**关键信息**：
- `context.conversation` 包含对话历史（从 `request.dialogs` 构建）
- 传递给 `reply_generator.generate_reply`

### 5. Prompt Assembler (`app/services/prompt_assembler.py`)

```python
# 第 248-280 行
def _infer_reply_sentence(self, messages: list[Any]) -> str:
    if not messages:
        return ""

    user_speakers = {"user", "用户", "我", "me"}

    # 第一遍：从后往前找第一个非 user 的消息
    for msg in reversed(messages):
        speaker, content = _get(msg)
        text = content.strip()
        if not text:
            continue
        if str(speaker).strip() not in user_speakers:
            return text  # 返回第一个非 user 的消息

    # 第二遍：如果没找到，返回最后一条消息
    for msg in reversed(messages):
        _, content = _get(msg)
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""
```

**问题**：
- 只检查 `speaker not in user_speakers`，会匹配空字符串（文字 content 的 speaker）
- 没有明确识别 "talker left"（应该是 `speaker == "talker"` 且 `from_user == False`）
- 不知道最后一个 content 的类型

### 6. Prompt Template (`prompts/versions/reply_generation_v3.3.txt`)

```
Last Message:
{last_message}
```

**关键信息**：
- `last_message` 由 `_infer_reply_sentence` 推断得出
- 用于生成回复的上下文

## 修改方案

### 方案概述

在 `_generate_reply` 函数中：
1. 追踪最后一个 content 的类型（从 `items` 列表获取）
2. 根据类型选择正确的 `reply_sentence`
3. 通过 `GenerateReplyRequest` 传递给 orchestrator

### 详细步骤

#### Step 1: 修改 `_generate_reply` 函数签名

**文件**: `app/api/v1/predict.py`

**位置**: 第 970 行

**修改前**:
```python
async def _generate_reply(
    request: PredictRequest,
    orchestrator: OrchestratorDep,
    analysis_queue:List[ImageAnalysisQueueInput]
) -> List[str]:
```

**修改后**:
```python
async def _generate_reply(
    request: PredictRequest,
    orchestrator: OrchestratorDep,
    analysis_queue: List[ImageAnalysisQueueInput],
    last_content_type: Literal["image", "text"],  # 新增：最后一个 content 的类型
    last_content_value: str,  # 新增：最后一个 content 的值（URL 或文字）
) -> List[str]:
```

#### Step 2: 在 `_generate_reply` 中根据类型选择 `reply_sentence`

**文件**: `app/api/v1/predict.py`

**位置**: 第 980-1005 行

**修改前**:
```python
for resource_index, (resources, dialog, list_image_result) in enumerate(analysis_queue):
    conversation = []
    for dialog_item in dialog:
        conversation.append({
            "speaker": dialog_item.speaker,
            "text": dialog_item.text,
        })
    
    orchestrator_request = GenerateReplyRequest(
        user_id=request.user_id,
        target_id="unknown",
        conversation_id=request.session_id,
        resources=resources,
        dialogs=conversation,
        language=request.language,
        quality="normal",
        persona=request.other_properties.lower(),
        scene=request.scene,
    )
    
    if resource_index < len(analysis_queue) - 1:
        await orchestrator.prepare_generate_reply(orchestrator_request)
        continue
    
    orchestrator_response = await orchestrator.generate_reply(orchestrator_request)
```

**修改后**:
```python
for resource_index, (resources, dialog, list_image_result) in enumerate(analysis_queue):
    conversation = []
    for dialog_item in dialog:
        conversation.append({
            "speaker": dialog_item.speaker,
            "text": dialog_item.text,
        })
    
    # 新增：根据最后一个 content 的类型选择 reply_sentence
    reply_sentence = ""
    if resource_index == len(analysis_queue) - 1:  # 只在最后一个组处理
        if last_content_type == "text":
            # 如果最后一个 content 是文字，直接使用文字内容
            reply_sentence = last_content_value
            logger.info(f"Last content is text, using text as reply_sentence: {reply_sentence[:50]}...")
        else:  # last_content_type == "image"
            # 如果最后一个 content 是图片，找 talker left 的最后一句话
            reply_sentence = _find_last_talker_left_message(dialog)
            logger.info(f"Last content is image, using talker left message as reply_sentence: {reply_sentence[:50]}...")
    
    orchestrator_request = GenerateReplyRequest(
        user_id=request.user_id,
        target_id="unknown",
        conversation_id=request.session_id,
        resources=resources,
        dialogs=conversation,
        language=request.language,
        quality="normal",
        persona=request.other_properties.lower(),
        scene=request.scene,
        reply_sentence=reply_sentence,  # 新增：传递 reply_sentence
    )
    
    if resource_index < len(analysis_queue) - 1:
        await orchestrator.prepare_generate_reply(orchestrator_request)
        continue
    
    orchestrator_response = await orchestrator.generate_reply(orchestrator_request)
```

#### Step 3: 添加 `_find_last_talker_left_message` 辅助函数

**文件**: `app/api/v1/predict.py`

**位置**: 在 `_generate_reply` 函数之前（约第 960 行）

**新增代码**:
```python
def _find_last_talker_left_message(dialogs: list[DialogItem]) -> str:
    """
    从 dialogs 中找到 talker left 的最后一句话。
    
    "talker left" 定义：
    - speaker 为 "talker"（不区分大小写）
    - from_user 为 False
    
    Args:
        dialogs: DialogItem 列表
    
    Returns:
        talker left 的最后一句话，如果没有找到则返回空字符串
    """
    # 从后往前遍历
    for dialog_item in reversed(dialogs):
        speaker = dialog_item.speaker.lower().strip()
        from_user = dialog_item.from_user
        text = dialog_item.text.strip()
        
        # 检查是否为 talker left
        if speaker == "talker" and from_user is False and text:
            logger.info(f"Found talker left message: {text[:50]}...")
            return text
    
    # 如果没有找到 talker left 的消息，返回空字符串
    logger.warning("No talker left message found in dialogs")
    return ""
```

#### Step 4: 修改 `handle_image` 中调用 `_generate_reply` 的地方

**文件**: `app/api/v1/predict.py`

**位置 1**: 第 1330-1340 行（merge_step 流程）

**修改前**:
```python
if request.reply:
    # Build analysis queue for reply generation
    # ...
    
    reply_start = time.time()
    suggested_replies = await _generate_reply(
        request,
        orchestrator,
        analysis_queue,
    )
    reply_duration_ms = int((time.time() - reply_start) * 1000)
```

**修改后**:
```python
if request.reply:
    # Build analysis queue for reply generation
    # ...
    
    # 新增：获取最后一个 content 的类型和值
    last_content_type = items[-1][0] if items else "text"
    last_content_value = items[-1][1] if items else ""
    
    reply_start = time.time()
    suggested_replies = await _generate_reply(
        request,
        orchestrator,
        analysis_queue,
        last_content_type,  # 新增
        last_content_value,  # 新增
    )
    reply_duration_ms = int((time.time() - reply_start) * 1000)
```

**位置 2**: 第 1470-1480 行（traditional 流程）

**修改前**:
```python
if request.reply and items:
    reply_start = time.time()
    suggested_replies = await _generate_reply(
        request,
        orchestrator,
        analysis_queue,
    )
    reply_duration_ms = int((time.time() - reply_start) * 1000)
```

**修改后**:
```python
if request.reply and items:
    # 新增：获取最后一个 content 的类型和值
    last_content_type = items[-1][0] if items else "text"
    last_content_value = items[-1][1] if items else ""
    
    reply_start = time.time()
    suggested_replies = await _generate_reply(
        request,
        orchestrator,
        analysis_queue,
        last_content_type,  # 新增
        last_content_value,  # 新增
    )
    reply_duration_ms = int((time.time() - reply_start) * 1000)
```

#### Step 5: 修改 `GenerateReplyRequest` 模型

**文件**: `app/models/api.py`

**位置**: `GenerateReplyRequest` 类定义

**修改前**:
```python
class GenerateReplyRequest(BaseModel):
    user_id: str
    target_id: str
    conversation_id: str
    resources: list[str]
    dialogs: list[dict]
    language: str = "zh"
    quality: str = "normal"
    persona: str = ""
    scene: int = 1
```

**修改后**:
```python
class GenerateReplyRequest(BaseModel):
    user_id: str
    target_id: str
    conversation_id: str
    resources: list[str]
    dialogs: list[dict]
    language: str = "zh"
    quality: str = "normal"
    persona: str = ""
    scene: int = 1
    reply_sentence: str = ""  # 新增：明确指定的 reply_sentence
```

#### Step 6: 修改 `PromptAssembler._infer_reply_sentence`

**文件**: `app/services/prompt_assembler.py`

**位置**: 第 248-280 行

**修改前**:
```python
def _infer_reply_sentence(self, messages: list[Any]) -> str:
    if not messages:
        return ""

    def _get(msg: Any) -> tuple[str, str]:
        if hasattr(msg, "speaker"):
            speaker = str(getattr(msg, "speaker", ""))
            content = str(getattr(msg, "content", ""))
        else:
            speaker = str(msg.get("speaker", ""))
            content = str(msg.get("content", ""))
        return speaker, content

    user_speakers = {"user", "用户", "我", "me"}

    for msg in reversed(messages):
        speaker, content = _get(msg)
        if not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        if str(speaker).strip() not in user_speakers:
            return text

    for msg in reversed(messages):
        _, content = _get(msg)
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""
```

**修改后**:
```python
def _infer_reply_sentence(self, messages: list[Any], explicit_reply_sentence: str = "") -> str:
    """
    推断 reply_sentence（Last Message）。
    
    优先级：
    1. 如果提供了 explicit_reply_sentence，直接使用
    2. 否则，使用原有逻辑（从后往前找第一个非 user 的消息）
    
    Args:
        messages: 对话消息列表
        explicit_reply_sentence: 明确指定的 reply_sentence（可选）
    
    Returns:
        推断出的 reply_sentence
    """
    # 优先使用明确指定的 reply_sentence
    if explicit_reply_sentence and explicit_reply_sentence.strip():
        logger.info(f"Using explicit reply_sentence: {explicit_reply_sentence[:50]}...")
        return explicit_reply_sentence.strip()
    
    # 原有逻辑（后备方案）
    if not messages:
        return ""

    def _get(msg: Any) -> tuple[str, str]:
        if hasattr(msg, "speaker"):
            speaker = str(getattr(msg, "speaker", ""))
            content = str(getattr(msg, "content", ""))
        else:
            speaker = str(msg.get("speaker", ""))
            content = str(msg.get("content", ""))
        return speaker, content

    user_speakers = {"user", "用户", "我", "me"}

    for msg in reversed(messages):
        speaker, content = _get(msg)
        if not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        if str(speaker).strip() not in user_speakers:
            logger.info(f"Inferred reply_sentence from conversation: {text[:50]}...")
            return text

    for msg in reversed(messages):
        _, content = _get(msg)
        if isinstance(content, str) and content.strip():
            logger.info(f"Fallback reply_sentence: {content.strip()[:50]}...")
            return content.strip()
    
    logger.warning("No reply_sentence found")
    return ""
```

#### Step 7: 修改 `PromptAssembler` 调用 `_infer_reply_sentence` 的地方

**文件**: `app/services/prompt_assembler.py`

**位置**: 需要搜索所有调用 `_infer_reply_sentence` 的地方

**修改**:
```python
# 修改前
last_message = self._infer_reply_sentence(context.conversation)

# 修改后
# 从 request 中获取 reply_sentence（如果有）
explicit_reply_sentence = getattr(request, "reply_sentence", "")
last_message = self._infer_reply_sentence(context.conversation, explicit_reply_sentence)
```

**注意**: 需要确保 `request` 对象在调用时可用，可能需要传递额外的参数。

#### Step 8: 修改 `ReplyGenerationInput` 模型（如果需要）

**文件**: `app/models/schemas.py`

**检查**: `ReplyGenerationInput` 是否需要添加 `reply_sentence` 字段

**如果需要**:
```python
class ReplyGenerationInput(BaseModel):
    user_id: str
    prompt: str
    quality: str
    context: ContextResult
    scene: SceneAnalysisResult
    persona: PersonaSnapshot
    language: str = "zh"
    reply_sentence: str = ""  # 新增
```

**然后在 `orchestrator._generate_with_retry` 中传递**:
```python
reply_input = ReplyGenerationInput(
    user_id=request.user_id,
    prompt=f"Generate a reply for conversation {request.conversation_id}",
    quality=quality,
    context=context,
    scene=scene,
    persona=persona,
    language=request.language,
    reply_sentence=getattr(request, "reply_sentence", ""),  # 新增
)
```

## 测试场景

### 场景 1: 纯图片（Scene 1）

**输入**:
```json
{
  "content": ["https://example.com/chat1.jpg"],
  "scene": 1,
  "reply": true
}
```

**期望**:
- `last_content_type` = "image"
- `reply_sentence` = 图片中 talker left 的最后一句话

### 场景 2: 混合 - 最后是图片（Scene 3）

**输入**:
```json
{
  "content": [
    "这是一段文字描述",
    "https://example.com/chat1.jpg"
  ],
  "scene": 3,
  "reply": true
}
```

**期望**:
- `last_content_type` = "image"
- `reply_sentence` = 图片中 talker left 的最后一句话

### 场景 3: 混合 - 最后是文字（Scene 3）

**输入**:
```json
{
  "content": [
    "https://example.com/chat1.jpg",
    "这是最后一段文字"
  ],
  "scene": 3,
  "reply": true
}
```

**期望**:
- `last_content_type` = "text"
- `reply_sentence` = "这是最后一段文字"

### 场景 4: 多个图片（Scene 1）

**输入**:
```json
{
  "content": [
    "https://example.com/chat1.jpg",
    "https://example.com/chat2.jpg"
  ],
  "scene": 1,
  "reply": true
}
```

**期望**:
- `last_content_type` = "image"
- `reply_sentence` = 最后一个图片中 talker left 的最后一句话

### 场景 5: 图片中没有 talker left 消息

**输入**:
```json
{
  "content": ["https://example.com/chat_only_user.jpg"],
  "scene": 1,
  "reply": true
}
```

**期望**:
- `last_content_type` = "image"
- `reply_sentence` = ""（空字符串）
- 日志警告: "No talker left message found in dialogs"

## 向后兼容性

### 兼容性考虑

1. **`GenerateReplyRequest.reply_sentence` 字段**:
   - 设置默认值为 `""`，保持向后兼容
   - 旧代码不传递此字段时，使用原有推断逻辑

2. **`_infer_reply_sentence` 方法**:
   - 添加 `explicit_reply_sentence` 参数，默认值为 `""`
   - 保持原有逻辑作为后备方案

3. **`_generate_reply` 函数**:
   - 添加两个新参数，但只在内部调用，不影响外部 API

### 迁移路径

1. **阶段 1**: 添加新字段和参数（保持向后兼容）
2. **阶段 2**: 更新调用代码，传递新参数
3. **阶段 3**: 测试和验证
4. **阶段 4**: 可选地移除旧逻辑（如果确认不再需要）

## 风险和注意事项

### 风险

1. **"talker left" 定义不明确**:
   - 当前假设 `speaker == "talker"` 且 `from_user == False`
   - 需要确认这是否符合实际数据

2. **图片中没有 talker left 消息**:
   - 当前方案返回空字符串
   - 可能需要后备逻辑（如返回最后一条消息）

3. **多个图片的处理**:
   - 当前方案只看最后一个 analysis_queue 元素的 dialogs
   - 需要确认这是否符合预期

### 注意事项

1. **日志记录**:
   - 添加详细的日志，记录 `last_content_type` 和 `reply_sentence` 的选择过程
   - 便于调试和验证

2. **错误处理**:
   - 如果 `items` 为空，需要处理边界情况
   - 如果 `dialogs` 为空，需要处理边界情况

3. **性能影响**:
   - 新增的逻辑很简单，性能影响可忽略

## 文档更新

### 需要更新的文档

1. **API 文档**:
   - 更新 `GenerateReplyRequest` 的字段说明
   - 添加 `reply_sentence` 字段的用途和示例

2. **架构文档**:
   - 更新 Last Message 的选择逻辑说明
   - 添加流程图（如果有）

3. **测试文档**:
   - 添加新的测试场景
   - 更新测试用例

4. **本文档**:
   - 作为修改方案的参考文档
   - 保留在 `docs/analysis/` 目录

## 总结

本方案通过以下步骤实现用户期望的 Last Message 选择逻辑：

1. 在 `_generate_reply` 中追踪最后一个 content 的类型
2. 根据类型选择正确的 `reply_sentence`
3. 通过 `GenerateReplyRequest.reply_sentence` 传递给 orchestrator
4. 在 `PromptAssembler._infer_reply_sentence` 中优先使用明确指定的 `reply_sentence`

**优点**:
- 明确区分图片和文字 content
- 准确识别 "talker left" 的最后一句话
- 保持向后兼容
- 代码改动最小化

**下一步**:
- 用户确认方案
- 实施代码修改
- 编写测试用例
- 验证和部署
