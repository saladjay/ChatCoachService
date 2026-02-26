# Last Message 修改 - 快速参考

## 核心逻辑（一句话）

**根据最后一个 content 的类型选择 Last Message：**
- **最后是文字** → 用文字本身
- **最后是图片** → 用图片中 talker/left 的最后一句话

---

## 关键确认点

| 问题 | 确认结果 |
|------|---------|
| Speaker 值 | `"talker"` / `"user"` 或 `"left"` / `"right"` |
| 识别逻辑 | `speaker.lower() in ("talker", "left")` |
| 没有 talker | 抛出 `HTTPException(400)` |
| 最后是图片 | 使用该图片的 dialogs 中 talker/left 的最后一句 |
| 最后是文字 | 使用该文字本身 |

---

## 核心代码

### 1. 查找 talker/left 消息
```python
def _find_last_talker_message(dialogs: list[DialogItem]) -> str:
    for dialog_item in reversed(dialogs):
        speaker = dialog_item.speaker.lower().strip()
        text = dialog_item.text.strip()
        
        if speaker in ("talker", "left") and text:
            return text
    
    raise HTTPException(status_code=400, detail="No talker message found...")
```

### 2. 选择 reply_sentence
```python
if last_content_type == "text":
    reply_sentence = last_content_value
else:  # image
    last_image_result = _find_last_image_result(list_image_result)
    reply_sentence = _find_last_talker_message(last_image_result.dialogs)
```

---

## 测试场景速查

| 场景 | Content | 最后一个 | 期望 Last Message |
|------|---------|---------|------------------|
| 纯图片 | `["img.jpg"]` | 图片 | 图片中 talker/left 的最后一句 |
| 最后是图片 | `["text", "img.jpg"]` | 图片 | 图片中 talker/left 的最后一句 |
| 最后是文字 | `["img.jpg", "text"]` | 文字 | `"text"` |
| 多个图片 | `["img1.jpg", "img2.jpg"]` | 图片 | img2.jpg 中 talker/left 的最后一句 |
| 复杂混合（图） | `["text1", "img2", "text3", "img4"]` | 图片 | img4 中 talker/left 的最后一句 |
| 复杂混合（文） | `["text1", "img2", "text3", "img4", "text5"]` | 文字 | `"text5"` |
| 无 talker | `["only_user.jpg"]` | 图片 | 抛出 400 错误 |

---

## 修改文件清单

- ✅ `app/api/v1/predict.py` - 主要修改（添加函数和逻辑）
- ✅ `app/models/api.py` - 添加 `reply_sentence` 字段
- ✅ `app/services/prompt_assembler.py` - 支持 explicit_reply_sentence
- ⚠️ `app/models/schemas.py` - 可能需要添加字段
- ⚠️ `app/services/orchestrator.py` - 可能需要传递参数

---

## 实施步骤（8 步）

1. 添加 `_find_last_talker_message()` 函数
2. 修改 `_generate_reply()` 函数签名（添加 2 个参数）
3. 在 `_generate_reply()` 中添加 reply_sentence 选择逻辑
4. 修改 `handle_image()` 调用 `_generate_reply()` 的地方（2 处）
5. 修改 `GenerateReplyRequest` 模型（添加字段）
6. 修改 `_infer_reply_sentence()` 方法（支持 explicit 参数）
7. 更新所有调用 `_infer_reply_sentence()` 的地方
8. 修改 `ReplyGenerationInput` 模型（如果需要）

---

## 详细文档

- **完整实施方案**：[final-implementation-plan.md](./final-implementation-plan.md)
- **数据流示例**：[data-flow-examples.md](./data-flow-examples.md)
- **问题分析**：[reply-sentence-logic-analysis.md](./reply-sentence-logic-analysis.md)
