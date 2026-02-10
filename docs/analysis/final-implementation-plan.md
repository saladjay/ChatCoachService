# Last Message 最终实施方案

## ✅ 用户确认的需求

根据用户确认，最终需求如下：

### 1. Speaker 的识别逻辑
**LLM 输出的 speaker 值有两种情况**：
- **情况 1**：`"left"` / `"right"` - 基于位置的分类
- **情况 2**：`"talker"` / `"user"` - 基于角色的分类

**可能的组合**：
- 有些图片可能都是 `"talker"`，只通过 `left`/`right` 区分
- 有些图片明确区分 `"user"` 和 `"talker"`

**识别规则**：
- 检查 `speaker.lower()` 是否为 `"talker"` 或 `"left"`
- 不需要检查 `from_user` 字段
- 使用 `.lower()` 处理大小写

### 2. 图片中没有 talker/left 消息的处理
**确认方案**：**严格模式 - 报错并阻止整个请求**
- 抛出 `HTTPException(status_code=400)`
- 错误信息：`"No talker message found in the image. The image must contain at least one message from the chat partner."`

### 3. 多个图片 + 文字混合场景
**确认规则**：
- 当最后一个 content 是**图片**时 → 使用该图片的 dialogs 中 talker/left 的最后一句话
- 当最后一个 content 是**文字**时 → 使用该文字本身

**示例**：
- `["text1", "image2", "text3", "image4"]` → 最后是图片 → 只看 `image4` 的 dialogs
- `["image1", "text2", "image3"]` → 最后是图片 → 只看 `image3` 的 dialogs
- `["text1", "text2", "image3"]` → 最后是图片 → 只看 `image3` 的 dialogs
- `["text1", "text2", "image3", "text4"]` → 最后是文字 → 使用 `"text4"`
### 4. 文字内容的判断
**确认**：当前 `_is_url()` 函数准确，可以区分 URL 和文字

---

## 实施方案

### Step 1: 添加辅助函数 `_find_last_talker_message`

**文件**: `app/api/v1/predict.py`

**位置**: 在 `_generate_reply` 函数之前（约第 960 行）

```python
def _find_last_talker_message(dialogs: list[DialogItem]) -> str:
    """
    从 dialogs 中找到 talker 或 left 的最后一句话。
    
    Args:
        dialogs: DialogItem 列表
    
    Returns:
        talker/left 的最后一句话
        
    Raises:
        HTTPException: 如果没有找到 talker/left 消息
    """
    for dialog_item in reversed(dialogs):
        speaker = dialog_item.speaker.lower().strip()
        text = dialog_item.text.strip()
        
        # 检查是否为 talker 或 left
        if speaker in ("talker", "left") and text:
            logger.info(f"Found talker/left message: {text[:50]}...")
            return text
    
    # 没找到 talker/left 消息，抛出异常
    logger.error("No talker/left message found in dialogs")
    raise HTTPException(
        status_code=400,
        detail="No talker message found in the image. The image must contain at least one message from the chat partner."
    )
```

### Step 2: 修改 `_generate_reply` 函数签名

**文件**: `app/api/v1/predict.py`

**位置**: 第 970 行

```python
async def _generate_reply(
    request: PredictRequest,
    orchestrator: OrchestratorDep,
    analysis_queue: List[ImageAnalysisQueueInput],
    last_content_type: Literal["image", "text"],  # 新增
    last_content_value: str,  # 新增
) -> List[str]:
```

### Step 3: 在 `_generate_reply` 中添加 reply_sentence 选择逻辑

**文件**: `app/api/v1/predict.py`

**位置**: 第 980-1005 行

```python
for resource_index, (resources, dialog, list_image_result) in enumerate(analysis_queue):
    # 构建 conversation
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
            # 文字：直接使用文字内容
            reply_sentence = last_content_value
            logger.info(f"Last content is text, using text as reply_sentence: {reply_sentence[:50]}...")
        else:  # image
            # 图片：找最后一个图片的 talker/left 消息
            # 从 list_image_result 中找最后一个图片类型的 result
            last_image_result = None
            for result in reversed(list_image_result):
                # 检查 result.content 是否为 URL（图片）
                if _is_url(result.content):
                    last_image_result = result
                    break
            
            if last_image_result:
                # 使用最后一个图片的 dialogs
                reply_sentence = _find_last_talker_message(last_image_result.dialogs)
                logger.info(f"Last content is image, using talker/left message from last image: {reply_sentence[:50]}...")
            else:
                # 没有找到图片类型的 result，使用所有 dialogs（后备方案）
                reply_sentence = _find_last_talker_message(dialog)
                logger.info(f"Last content is image, using talker/left message from all dialogs: {reply_sentence[:50]}...")
    
    orchestrator_request = GenerateReplyRequest(
        user_id=request.user_id,
        target_id="unknown",
        conversation_id=request.session_id,
        resources=resources,
        dialogs=conversation,
        language=request.language,
        quality="normal",
        persona=request.other_properties.lower() if request.other_properties else "",
        scene=request.scene,
        reply_sentence=reply_sentence,  # 新增
    )
    
    if resource_index < len(analysis_queue) - 1:
        await orchestrator.prepare_generate_reply(orchestrator_request)
        continue
    
    orchestrator_response = await orchestrator.generate_reply(orchestrator_request)
    # ... 后续处理 ...
```

### Step 4: 修改 `handle_image` 中调用 `_generate_reply` 的地方

**文件**: `app/api/v1/predict.py`

**位置 1**: 第 1330-1340 行（merge_step 流程）

```python
if request.reply:
    # Build analysis queue for reply generation
    # ... 构建 analysis_queue 的代码 ...
    
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
    # ...
```

**位置 2**: 第 1470-1480 行（traditional 流程）

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
    # ...
```

### Step 5: 修改 `GenerateReplyRequest` 模型

**文件**: `app/models/api.py`

**位置**: `GenerateReplyRequest` 类定义

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

### Step 6: 修改 `PromptAssembler._infer_reply_sentence`

**文件**: `app/services/prompt_assembler.py`

**位置**: 第 248-280 行

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

    user_speakers = {"user", "用户", "我", "me", "right"}  # 添加 "right"

    for msg in reversed(messages):
        speaker, content = _get(msg)
        if not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        if str(speaker).strip().lower() not in user_speakers:
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

### Step 7: 更新 `PromptAssembler` 调用 `_infer_reply_sentence` 的地方

**文件**: `app/services/prompt_assembler.py`

需要搜索所有调用 `_infer_reply_sentence` 的地方，并传递 `explicit_reply_sentence` 参数。

**示例**：
```python
# 从 input 或 request 中获取 reply_sentence
explicit_reply_sentence = ""
if hasattr(input, "reply_sentence"):
    explicit_reply_sentence = input.reply_sentence
elif hasattr(input, "request") and hasattr(input.request, "reply_sentence"):
    explicit_reply_sentence = input.request.reply_sentence

last_message = self._infer_reply_sentence(context.conversation, explicit_reply_sentence)
```

**注意**：需要检查 `ReplyGenerationInput` 是否需要添加 `reply_sentence` 字段。

### Step 8: 修改 `ReplyGenerationInput` 模型（如果需要）

**文件**: `app/models/schemas.py`

**检查并添加**：
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

**然后在 `orchestrator._generate_with_retry` 中传递**：
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

---

## 测试场景

### 场景 1: 纯图片（speaker = "talker"）
```json
{"content": ["chat.jpg"], "scene": 1, "reply": true}
```
- 图片中有 `speaker="talker"` 的消息
- 期望：`reply_sentence` = talker 的最后一句话

### 场景 2: 纯图片（speaker = "left"）
```json
{"content": ["chat.jpg"], "scene": 1, "reply": true}
```
- 图片中只有 `speaker="left"` 和 `speaker="right"`
- 期望：`reply_sentence` = left 的最后一句话

### 场景 3: 混合 - 最后是图片
```json
{"content": ["文字描述", "chat.jpg"], "scene": 3, "reply": true}
```
- 期望：`reply_sentence` = 图片中 talker/left 的最后一句话

### 场景 4: 混合 - 最后是文字
```json
{"content": ["chat.jpg", "这是最后一段文字"], "scene": 3, "reply": true}
```
- 期望：`reply_sentence` = "这是最后一段文字"

### 场景 5: 多个图片
```json
{"content": ["chat1.jpg", "chat2.jpg"], "scene": 1, "reply": true}
```
- 期望：`reply_sentence` = 最后一个图片（chat2.jpg）中 talker/left 的最后一句话

### 场景 6: 复杂混合 - 最后是图片
```json
{"content": ["text1", "image2", "text3", "image4"], "scene": 3, "reply": true}
```
- 最后一个 content 是图片（image4）
- 期望：`reply_sentence` = image4 中 talker/left 的最后一句话

### 场景 6b: 复杂混合 - 最后是文字
```json
{"content": ["text1", "image2", "text3", "image4", "text5"], "scene": 3, "reply": true}
```
- 最后一个 content 是文字（text5）
- 期望：`reply_sentence` = "text5"

### 场景 7: 图片中没有 talker/left 消息
```json
{"content": ["only_user_messages.jpg"], "scene": 1, "reply": true}
```
- 最后一个 content 是图片，但图片中只有 user/right 的消息
- 期望：抛出 `HTTPException(400, "No talker message found...")`

---

## 关键代码变更总结

### 新增代码
1. `_find_last_talker_message()` 函数 - 查找 talker/left 的最后一句话
2. `_generate_reply()` 函数添加两个参数：`last_content_type`, `last_content_value`
3. `GenerateReplyRequest` 添加字段：`reply_sentence`
4. `ReplyGenerationInput` 添加字段：`reply_sentence`（如果需要）

### 修改代码
1. `_generate_reply()` 函数内部逻辑 - 根据类型选择 reply_sentence
2. `handle_image()` 函数 - 传递 last_content_type 和 last_content_value
3. `_infer_reply_sentence()` 方法 - 支持 explicit_reply_sentence 参数
4. 所有调用 `_infer_reply_sentence()` 的地方 - 传递 explicit_reply_sentence

### 涉及文件
- `app/api/v1/predict.py` - 主要修改
- `app/models/api.py` - 添加字段
- `app/models/schemas.py` - 添加字段（如果需要）
- `app/services/prompt_assembler.py` - 修改方法
- `app/services/orchestrator.py` - 传递参数（如果需要）

---

## 向后兼容性

✅ **完全向后兼容**：
- 所有新增字段都有默认值 `""`
- 如果不传递新参数，使用原有推断逻辑
- 不影响现有 API 调用

---

## 下一步

1. ✅ 用户确认需求（已完成）
2. ⏳ 实施代码修改
3. ⏳ 添加详细日志
4. ⏳ 编写测试用例
5. ⏳ 验证和部署
