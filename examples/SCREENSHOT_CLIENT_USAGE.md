# Screenshot Analysis Client 使用指南

本文档介绍如何使用客户端调用第三方API完成screenshot analysis。

## 📋 目录

- [快速开始](#快速开始)
- [完整客户端](#完整客户端)
- [简单示例](#简单示例)
- [API说明](#api说明)
- [常见问题](#常见问题)

## 🚀 快速开始

### 1. 启动服务器

```bash
# 确保已安装依赖
pip install -r requirements.txt

# 启动API服务器
python main.py
```

服务器将在 `http://localhost:8000` 启动。

### 2. 运行简单示例

```bash
# 运行简单示例（使用模拟数据）
python examples/simple_screenshot_client.py
```

### 3. 使用完整客户端

```bash
# 只分析截图
python examples/screenshot_analysis_client.py --image path/to/screenshot.png --mode analyze

# 分析截图并生成回复
python examples/screenshot_analysis_client.py --image path/to/screenshot.png --mode reply
```

## 📱 完整客户端

### 功能特性

- ✅ 支持本地图片路径输入
- ✅ 自动上传图片到服务器
- ✅ 调用screenshot parse API
- ✅ 两种模式：只分析 / 分析+生成回复
- ✅ 详细的结果展示
- ✅ 支持保存结果到JSON文件

### 使用方法

#### 基本用法

```bash
# 只分析截图
python examples/screenshot_analysis_client.py \
    --image screenshot.png \
    --mode analyze

# 分析截图并生成回复
python examples/screenshot_analysis_client.py \
    --image screenshot.png \
    --mode reply
```

#### 高级选项

```bash
# 指定服务器地址
python examples/screenshot_analysis_client.py \
    --image screenshot.png \
    --mode reply \
    --server http://api.example.com

# 自定义亲密度和语言
python examples/screenshot_analysis_client.py \
    --image screenshot.png \
    --mode reply \
    --intimacy 70 \
    --language zh-CN \
    --quality premium

# 保存结果到文件
python examples/screenshot_analysis_client.py \
    --image screenshot.png \
    --mode reply \
    --output result.json
```

#### 完整参数列表

| 参数 | 说明 | 默认值 | 必需 |
|------|------|--------|------|
| `--image` | 本地图片路径 | - | ✅ |
| `--mode` | 运行模式 (analyze/reply) | analyze | ❌ |
| `--server` | API服务器地址 | http://localhost:8000 | ❌ |
| `--intimacy` | 亲密度值 (0-100) | 50 | ❌ |
| `--language` | 回复语言 | zh-CN | ❌ |
| `--quality` | 生成质量 (cheap/normal/premium) | normal | ❌ |
| `--output` | 保存结果到JSON文件 | - | ❌ |

### 输出示例

#### 分析模式输出

```
================================================================================
📊 分析结果
================================================================================

📷 图片信息:
   尺寸: 750x1334

👥 参与者:
   自己: 我 (ID: user_123)
   对方: 小明 (ID: friend_456)

📐 布局:
   类型: two_columns
   左侧: talker
   右侧: user

💬 对话内容 (3 条消息):

   1. 👤 USER
      文本: 你好！最近怎么样？
      位置: (600, 125)
      置信度: 95.0%

   2. 👥 TALKER
      文本: 挺好的，谢谢！你呢？
      位置: (150, 195)
      置信度: 92.0%

   3. 👤 USER
      文本: 一起喝咖啡吗？
      位置: (600, 265)
      置信度: 88.0%

================================================================================
```

#### 回复模式输出

```
================================================================================
💬 生成的回复
================================================================================

好啊！什么时候方便？我这周末都有空。

📊 元数据:
   置信度: 0.85
   亲密度(前): 3
   亲密度(后): 3
   模型: qwen-plus
   提供商: dashscope
   成本: $0.0020
   是否降级: 否

================================================================================
```

## 🔧 简单示例

如果你只想快速测试API调用，可以使用简单示例：

```bash
python examples/simple_screenshot_client.py
```

这个脚本包含两个示例：
1. **示例1**: 只分析截图
2. **示例2**: 分析截图 + 生成回复

### 代码示例

```python
import asyncio
import httpx

async def analyze_screenshot():
    """分析截图"""
    server_url = "http://localhost:8000"
    parse_endpoint = f"{server_url}/api/v1/chat_screenshot/parse"
    
    request_data = {
        "image_url": "https://example.com/screenshot.png",
        "session_id": "demo-001",
        "options": {
            "need_nickname": true,
            "need_sender": true,
            "force_two_columns": true
        }
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(parse_endpoint, json=request_data)
        result = response.json()
        
        if result["code"] == 0:
            print("✅ 分析成功!")
            # 处理结果...
        else:
            print(f"❌ 分析失败: {result['msg']}")

asyncio.run(analyze_screenshot())
```

## 📚 API说明

### 1. Screenshot Parse API

**端点**: `POST /api/v1/chat_screenshot/parse`

**请求格式**:
```json
{
  "image_url": "https://example.com/screenshot.png",
  "session_id": "optional-session-id",
  "options": {
    "need_nickname": true,
    "need_sender": true,
    "force_two_columns": true
  }
}
```

**响应格式**:
```json
{
  "code": 0,
  "msg": "Success",
  "data": {
    "image_meta": {
      "width": 750,
      "height": 1334
    },
    "participants": {
      "self": {
        "id": "user_123",
        "nickname": "我"
      },
      "other": {
        "id": "friend_456",
        "nickname": "小明"
      }
    },
    "bubbles": [
      {
        "bubble_id": "b1",
        "bbox": {"x1": 50, "y1": 100, "x2": 300, "y2": 150},
        "center_x": 175,
        "center_y": 125,
        "text": "你好！",
        "sender": "user",
        "column": "right",
        "confidence": 0.95
      }
    ],
    "layout": {
      "type": "two_columns",
      "left_role": "talker",
      "right_role": "user"
    }
  }
}
```

### 2. Generate Reply API

**端点**: `POST /api/v1/generate_reply`

**请求格式**:
```json
{
  "user_id": "user_123",
  "target_id": "friend_456",
  "conversation_id": "conv_001",
  "dialogs": [
    {
      "speaker": "user",
      "text": "你好！",
      "timestamp": null
    }
  ],
  "intimacy_value": 50,
  "language": "zh-CN",
  "quality": "normal"
}
```

**响应格式**:
```json
{
  "reply_text": "你好！很高兴见到你。",
  "confidence": 0.85,
  "intimacy_level_before": 3,
  "intimacy_level_after": 3,
  "model": "qwen-plus",
  "provider": "dashscope",
  "cost_usd": 0.002,
  "fallback": false
}
```

## ❓ 常见问题

### Q1: 如何上传本地图片？

**A**: 在生产环境中，你需要：

1. 将图片上传到云存储（如AWS S3, 阿里云OSS等）
2. 获取公开访问的URL
3. 使用该URL调用API

示例代码（使用阿里云OSS）:

```python
import oss2

# 初始化OSS客户端
auth = oss2.Auth('your-access-key', 'your-secret-key')
bucket = oss2.Bucket(auth, 'your-endpoint', 'your-bucket')

# 上传图片
with open('screenshot.png', 'rb') as f:
    bucket.put_object('screenshots/screenshot.png', f)

# 获取URL
image_url = f"https://your-bucket.your-endpoint/screenshots/screenshot.png"
```

### Q2: 支持哪些图片格式？

**A**: 支持以下格式：
- PNG
- JPEG/JPG
- WebP

### Q3: 图片大小有限制吗？

**A**: 建议：
- 文件大小: < 10MB
- 分辨率: 建议 1080p 以下
- 过大的图片会增加处理时间和成本

### Q4: 如何处理错误？

**A**: API返回的错误码：

| 错误码 | 说明 | 处理方法 |
|--------|------|----------|
| 1001 | 图片下载失败 | 检查URL是否有效，图片是否可访问 |
| 1002 | LLM调用失败 | 检查API密钥，重试请求 |
| 1003 | JSON解析失败 | LLM返回格式错误，重试请求 |
| 1004 | 缺少必需字段 | LLM输出不完整，重试请求 |

### Q5: 如何提高分析准确度？

**A**: 建议：

1. **指定应用类型**: 使用 `--app-type` 参数
2. **清晰的截图**: 确保文字清晰可读
3. **完整的对话**: 包含完整的聊天气泡
4. **标准布局**: 使用标准的聊天界面布局

### Q6: 支持哪些聊天应用？

**A**: 目前支持：
- ✅ WeChat (微信)
- ✅ WhatsApp
- ✅ LINE
- ✅ 其他标准两列布局的聊天应用

### Q7: 如何批量处理多张截图？

**A**: 示例代码：

```python
import asyncio
from pathlib import Path

async def batch_analyze(image_dir: str):
    """批量分析截图"""
    client = ScreenshotAnalysisClient()
    
    # 获取所有图片
    images = list(Path(image_dir).glob("*.png"))
    
    # 并发处理
    tasks = []
    for image in images:
        image_url = await client.upload_image(str(image))
        task = client.analyze_screenshot(image_url)
        tasks.append(task)
    
    # 等待所有任务完成
    results = await asyncio.gather(*tasks)
    return results

# 使用
results = asyncio.run(batch_analyze("screenshots/"))
```

## 📞 技术支持

如有问题，请：
1. 查看 [API文档](../README.md)
2. 查看 [示例代码](.)
3. 提交 Issue

## 📄 许可证

本项目采用 MIT 许可证。
