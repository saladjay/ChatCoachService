# Last Message 数据流示例

本文档通过具体示例说明不同场景下的数据流和 Last Message 选择逻辑。

---

## 场景 1: 纯图片

### 输入
```json
{
  "content": ["https://example.com/chat.jpg"],
  "scene": 1,
  "reply": true
}
```

### 数据流

#### Step 1: Content 处理
```python
items = [
    ("image", "https://example.com/chat.jpg", ImageResult{
        content: "https://example.com/chat.jpg",
        dialogs: [
            DialogItem{speaker: "user", text: "你好", from_user: True},
            DialogItem{speaker: "talker", text: "你好啊", from_user: False},
            DialogItem{speaker: "user", text: "在干嘛", from_user: True},
            DialogItem{speaker: "talker", text: "在工作", from_user: False},
        ]
    })
]
```

#### Step 2: Analysis Queue 构建
```python
analysis_queue = [
    (
        ["https://example.com/chat.jpg"],  # resources
        [  # dialogs
            {speaker: "user", text: "你好"},
            {speaker: "talker", text: "你好啊"},
            {speaker: "user", text: "在干嘛"},
            {speaker: "talker", text: "在工作"},
        ],
        [ImageResult{...}]  # list_image_result
    )
]
```

#### Step 3: Reply Generation
```python
last_content_type = "image"  # items[-1][0]
last_content_value = "https://example.com/chat.jpg"  # items[-1][1]

# 因为 last_content_type == "image"
# 从 dialogs 中找 talker 的最后一句话
reply_sentence = _find_last_talker_message(dialogs)
# 结果: "在工作"
```

### 结果
- `last_content_type` = `"image"`
- `reply_sentence` = `"在工作"`

---

## 场景 2: 混合 - 最后是图片

### 输入
```json
{
  "content": [
    "这是一段文字描述",
    "https://example.com/chat.jpg"
  ],
  "scene": 3,
  "reply": true
}
```

### 数据流

#### Step 1: Content 处理
```python
items = [
    ("text", "这是一段文字描述", ImageResult{
        content: "这是一段文字描述",
        dialogs: [
            DialogItem{speaker: "", text: "这是一段文字描述", from_user: False}
        ]
    }),
    ("image", "https://example.com/chat.jpg", ImageResult{
        content: "https://example.com/chat.jpg",
        dialogs: [
            DialogItem{speaker: "user", text: "你好", from_user: True},
            DialogItem{speaker: "talker", text: "你好啊", from_user: False},
        ]
    })
]
```

#### Step 2: Analysis Queue 构建
```python
analysis_queue = [
    (
        ["这是一段文字描述", "https://example.com/chat.jpg"],  # resources
        [  # dialogs（合并了文字和图片的 dialogs）
            {speaker: "", text: "这是一段文字描述"},
            {speaker: "user", text: "你好"},
            {speaker: "talker", text: "你好啊"},
        ],
        [  # list_image_result
            ImageResult{content: "这是一段文字描述", dialogs: [...]},
            ImageResult{content: "https://example.com/chat.jpg", dialogs: [...]},
        ]
    )
]
```

#### Step 3: Reply Generation
```python
last_content_type = "image"  # items[-1][0]
last_content_value = "https://example.com/chat.jpg"  # items[-1][1]

# 因为 last_content_type == "image"
# 需要从 list_image_result 中找到最后一个图片的 result
last_image_result = None
for result in reversed(list_image_result):
    if _is_url(result.content):  # 检查是否为 URL
        last_image_result = result
        break

# last_image_result.content = "https://example.com/chat.jpg"
# last_image_result.dialogs = [
#     DialogItem{speaker: "user", text: "你好", from_user: True},
#     DialogItem{speaker: "talker", text: "你好啊", from_user: False},
# ]

reply_sentence = _find_last_talker_message(last_image_result.dialogs)
# 结果: "你好啊"
```

### 结果
- `last_content_type` = `"image"`
- `reply_sentence` = `"你好啊"`（来自图片，不是文字）

---

## 场景 3: 混合 - 最后是文字

### 输入
```json
{
  "content": [
    "https://example.com/chat.jpg",
    "这是最后一段文字"
  ],
  "scene": 3,
  "reply": true
}
```

### 数据流

#### Step 1: Content 处理
```python
items = [
    ("image", "https://example.com/chat.jpg", ImageResult{
        content: "https://example.com/chat.jpg",
        dialogs: [
            DialogItem{speaker: "user", text: "你好", from_user: True},
            DialogItem{speaker: "talker", text: "你好啊", from_user: False},
        ]
    }),
    ("text", "这是最后一段文字", ImageResult{
        content: "这是最后一段文字",
        dialogs: [
            DialogItem{speaker: "", text: "这是最后一段文字", from_user: False}
        ]
    })
]
```

#### Step 2: Analysis Queue 构建
```python
analysis_queue = [
    (
        ["https://example.com/chat.jpg"],  # 第一组（图片）
        [
            {speaker: "user", text: "你好"},
            {speaker: "talker", text: "你好啊"},
        ],
        [ImageResult{content: "https://example.com/chat.jpg", ...}]
    ),
    (
        ["这是最后一段文字"],  # 第二组（文字）
        [
            {speaker: "", text: "这是最后一段文字"},
        ],
        [ImageResult{content: "这是最后一段文字", ...}]
    )
]
```

#### Step 3: Reply Generation
```python
last_content_type = "text"  # items[-1][0]
last_content_value = "这是最后一段文字"  # items[-1][1]

# 因为 last_content_type == "text"
# 直接使用文字内容
reply_sentence = last_content_value
# 结果: "这是最后一段文字"
```

### 结果
- `last_content_type` = `"text"`
- `reply_sentence` = `"这是最后一段文字"`

---

## 场景 4: 多个图片

### 输入
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

### 数据流

#### Step 1: Content 处理
```python
items = [
    ("image", "https://example.com/chat1.jpg", ImageResult{
        content: "https://example.com/chat1.jpg",
        dialogs: [
            DialogItem{speaker: "user", text: "早上好", from_user: True},
            DialogItem{speaker: "talker", text: "早", from_user: False},
        ]
    }),
    ("image", "https://example.com/chat2.jpg", ImageResult{
        content: "https://example.com/chat2.jpg",
        dialogs: [
            DialogItem{speaker: "user", text: "在干嘛", from_user: True},
            DialogItem{speaker: "talker", text: "在工作", from_user: False},
        ]
    })
]
```

#### Step 2: Analysis Queue 构建
```python
analysis_queue = [
    (
        ["https://example.com/chat1.jpg"],  # 第一组
        [
            {speaker: "user", text: "早上好"},
            {speaker: "talker", text: "早"},
        ],
        [ImageResult{content: "https://example.com/chat1.jpg", ...}]
    ),
    (
        ["https://example.com/chat2.jpg"],  # 第二组（最后一组）
        [
            {speaker: "user", text: "在干嘛"},
            {speaker: "talker", text: "在工作"},
        ],
        [ImageResult{content: "https://example.com/chat2.jpg", ...}]
    )
]
```

#### Step 3: Reply Generation
```python
last_content_type = "image"  # items[-1][0]
last_content_value = "https://example.com/chat2.jpg"  # items[-1][1]

# 只处理最后一个组（analysis_queue[-1]）
# 该组的 dialogs 只包含 chat2.jpg 的对话

reply_sentence = _find_last_talker_message(dialogs)
# 结果: "在工作"（来自 chat2.jpg，不是 chat1.jpg）
```

### 结果
- `last_content_type` = `"image"`
- `reply_sentence` = `"在工作"`（来自最后一个图片）

---

## 场景 5: 多个图片 + 文字混合

### 输入
```json
{
  "content": [
    "https://example.com/chat1.jpg",
    "中间的文字描述",
    "https://example.com/chat2.jpg"
  ],
  "scene": 3,
  "reply": true
}
```

### 数据流

#### Step 1: Content 处理
```python
items = [
    ("image", "https://example.com/chat1.jpg", ImageResult{...}),
    ("text", "中间的文字描述", ImageResult{...}),
    ("image", "https://example.com/chat2.jpg", ImageResult{...})
]
```

#### Step 2: Analysis Queue 构建
```python
analysis_queue = [
    (
        ["https://example.com/chat1.jpg"],  # 第一组（图片）
        [...],
        [ImageResult{content: "https://example.com/chat1.jpg", ...}]
    ),
    (
        ["中间的文字描述", "https://example.com/chat2.jpg"],  # 第二组（文字+图片）
        [
            {speaker: "", text: "中间的文字描述"},
            {speaker: "user", text: "在干嘛"},
            {speaker: "talker", text: "在工作"},
        ],
        [
            ImageResult{content: "中间的文字描述", ...},
            ImageResult{content: "https://example.com/chat2.jpg", ...}
        ]
    )
]
```

#### Step 3: Reply Generation
```python
last_content_type = "image"  # items[-1][0]
last_content_value = "https://example.com/chat2.jpg"  # items[-1][1]

# 只处理最后一个组
# list_image_result 包含两个 result（文字和图片）
# 需要找到最后一个图片的 result

last_image_result = None
for result in reversed(list_image_result):
    if _is_url(result.content):
        last_image_result = result
        break

# last_image_result.content = "https://example.com/chat2.jpg"
reply_sentence = _find_last_talker_message(last_image_result.dialogs)
# 结果: "在工作"
```

### 结果
- `last_content_type` = `"image"`
- `reply_sentence` = `"在工作"`（来自 chat2.jpg）

---

## 场景 6: 图片中没有 talker 消息

### 输入
```json
{
  "content": ["https://example.com/only_user.jpg"],
  "scene": 1,
  "reply": true
}
```

### 数据流

#### Step 1: Content 处理
```python
items = [
    ("image", "https://example.com/only_user.jpg", ImageResult{
        content: "https://example.com/only_user.jpg",
        dialogs: [
            DialogItem{speaker: "user", text: "你好", from_user: True},
            DialogItem{speaker: "user", text: "在吗", from_user: True},
            DialogItem{speaker: "user", text: "？", from_user: True},
        ]
    })
]
```

#### Step 3: Reply Generation
```python
last_content_type = "image"
last_content_value = "https://example.com/only_user.jpg"

# 尝试找 talker 消息
reply_sentence = _find_last_talker_message(dialogs)

# 遍历 dialogs，没有找到 speaker == "talker" 的消息
# 方案 A（严格模式）：抛出 HTTPException(400)
# 方案 B（宽松模式）：返回 ""，记录警告
```

### 结果（方案 A - 严格模式）
- 抛出异常：`HTTPException(status_code=400, detail="No talker message found...")`
- 请求失败

### 结果（方案 B - 宽松模式）⭐ 推荐
- `last_content_type` = `"image"`
- `reply_sentence` = `""`（空字符串）
- 日志警告：`"No talker message found in dialogs, using empty string"`
- 请求继续，LLM 处理空的 Last Message

---

## 关键逻辑总结

### 1. 类型判断
```python
last_content_type = items[-1][0]  # "image" 或 "text"
last_content_value = items[-1][1]  # URL 或文字内容
```

### 2. Reply Sentence 选择
```python
if last_content_type == "text":
    # 文字：直接使用
    reply_sentence = last_content_value
else:  # image
    # 图片：找最后一个图片的 talker 消息
    last_image_result = _find_last_image_result(list_image_result)
    reply_sentence = _find_last_talker_message(last_image_result.dialogs)
```

### 3. 找最后一个图片的 Result
```python
def _find_last_image_result(list_image_result):
    for result in reversed(list_image_result):
        if _is_url(result.content):
            return result
    return None
```

### 4. 找 Talker 的最后一句话
```python
def _find_last_talker_message(dialogs):
    for dialog_item in reversed(dialogs):
        speaker = dialog_item.speaker.lower().strip()
        text = dialog_item.text.strip()
        
        if speaker == "talker" and text:
            return text
    
    # 方案 A: raise HTTPException(400, ...)
    # 方案 B: return ""
```

---

## 需要确认的问题

请参考 [confirmation-needed.md](./confirmation-needed.md) 确认：
1. "talker" 的识别逻辑
2. 图片中没有 talker 消息的处理（方案 A 还是方案 B）
3. 多个图片 + 文字混合场景的逻辑
4. 文字内容的判断逻辑
