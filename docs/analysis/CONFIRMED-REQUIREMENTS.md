# ✅ 已确认的需求

## 核心规则

### Last Message 选择逻辑

```
IF 最后一个 content 是文字:
    Last Message = 该文字本身
ELSE IF 最后一个 content 是图片:
    Last Message = 该图片中 talker/left 的最后一句话
    IF 图片中没有 talker/left:
        抛出 HTTPException(400)
```

---

## 详细确认

### 1. Speaker 识别 ✅

**LLM 输出的 speaker 值**：
- **情况 1**：`"talker"` / `"user"` - 基于角色
- **情况 2**：`"left"` / `"right"` - 基于位置

**识别逻辑**：
```python
speaker.lower() in ("talker", "left")
```

**说明**：
- 不需要检查 `from_user` 字段
- 使用 `.lower()` 处理大小写
- 没有其他可能的 speaker 值

---

### 2. 没有 talker/left 消息 ✅

**处理方式**：严格模式 - 报错并阻止整个请求

**实现**：
```python
raise HTTPException(
    status_code=400,
    detail="No talker message found in the image. The image must contain at least one message from the chat partner."
)
```

---

### 3. 混合场景 ✅

**规则**：只看**最后一个 content** 的类型和内容

**示例**：

| Content 数组 | 最后一个 | Last Message 来源 |
|-------------|---------|------------------|
| `["text1", "image2", "text3", "image4"]` | image4 | image4 的 dialogs |
| `["text1", "image2", "text3", "image4", "text5"]` | text5 | text5 本身 |
| `["image1", "text2", "image3"]` | image3 | image3 的 dialogs |
| `["text1", "text2", "image3"]` | image3 | image3 的 dialogs |
| `["text1", "text2", "image3", "text4"]` | text4 | text4 本身 |

**关键点**：
- 不管前面有多少图片或文字
- 只看最后一个 content
- 根据最后一个的类型决定 Last Message

---

### 4. 文字判断 ✅

**判断方法**：`_is_url()` 函数

```python
def _is_url(content: str) -> bool:
    try:
        parsed = urlparse(content)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False
```

**确认**：准确，可以区分 URL 和文字

---

## 测试用例

### ✅ 通过的场景

| # | Content | 最后一个 | 期望 Last Message |
|---|---------|---------|------------------|
| 1 | `["img.jpg"]` | 图片 | img.jpg 中 talker/left 的最后一句 |
| 2 | `["text", "img.jpg"]` | 图片 | img.jpg 中 talker/left 的最后一句 |
| 3 | `["img.jpg", "text"]` | 文字 | `"text"` |
| 4 | `["img1.jpg", "img2.jpg"]` | 图片 | img2.jpg 中 talker/left 的最后一句 |
| 5 | `["text1", "img2", "text3", "img4"]` | 图片 | img4 中 talker/left 的最后一句 |
| 6 | `["text1", "img2", "text3", "img4", "text5"]` | 文字 | `"text5"` |

### ❌ 应该报错的场景

| # | Content | 原因 | 期望错误 |
|---|---------|------|---------|
| 1 | `["only_user.jpg"]` | 图片中只有 user/right 消息 | HTTPException(400) |

---

## 实施清单

- [ ] 添加 `_find_last_talker_message()` 函数
- [ ] 修改 `_generate_reply()` 函数（添加参数和逻辑）
- [ ] 修改 `handle_image()` 函数（传递参数）
- [ ] 修改 `GenerateReplyRequest` 模型（添加字段）
- [ ] 修改 `PromptAssembler._infer_reply_sentence()` 方法
- [ ] 更新所有调用点
- [ ] 编写测试用例
- [ ] 验证所有场景

---

## 相关文档

- **实施方案**：[final-implementation-plan.md](./final-implementation-plan.md)
- **快速参考**：[QUICK-REFERENCE.md](./QUICK-REFERENCE.md)
- **数据流示例**：[data-flow-examples.md](./data-flow-examples.md)
