# Screenshot Analysis Client 示例集合

本目录包含了调用第三方API完成screenshot analysis的完整示例代码。

## 📁 文件说明

### 1. 演示脚本

| 文件 | 说明 | 使用场景 |
|------|------|----------|
| `demo_screenshot_flow.py` | 完整流程演示（使用mock数据） | 快速了解完整流程，无需启动服务器 |
| `simple_screenshot_client.py` | 简单API调用示例 | 学习基本API调用方法 |
| `screenshot_analysis_client.py` | 完整功能客户端 | 生产环境使用，支持命令行参数 |

### 2. 文档

| 文件 | 说明 |
|------|------|
| `SCREENSHOT_CLIENT_USAGE.md` | 详细使用文档 |
| `screenshot_to_reply_example.py` | 集成示例（已存在） |

## 🚀 快速开始

### 方式1: 运行演示脚本（推荐新手）

```bash
# 无需启动服务器，使用mock数据演示完整流程
python examples/demo_screenshot_flow.py
```

这个脚本会展示：
- ✅ 场景1: 只分析截图
- ✅ 场景2: 分析截图 + 生成回复
- ✅ 场景3: 不同聊天应用（WeChat, WhatsApp, LINE）
- ✅ 场景4: 错误处理说明

### 方式2: 使用简单客户端

```bash
# 需要先启动服务器
python main.py

# 在另一个终端运行
python examples/simple_screenshot_client.py
```

### 方式3: 使用完整客户端

```bash
# 启动服务器
python main.py

# 使用完整客户端
python examples/screenshot_analysis_client.py --image path/to/screenshot.png --mode analyze
```

## 📖 使用示例

### 示例1: 只分析截图

```bash
python examples/screenshot_analysis_client.py \
    --image screenshots/wechat.png \
    --mode analyze \
    --app-type wechat
```

**输出**:
```
================================================================================
📊 分析结果
================================================================================

📷 图片信息:
   尺寸: 750x1334

👥 参与者:
   自己: 我 (ID: user_123)
   对方: 小明 (ID: friend_456)

💬 对话内容 (3 条消息):
   1. [我] 你好！最近怎么样？
   2. [对方] 挺好的，谢谢！
   3. [我] 一起喝咖啡吗？
```

### 示例2: 分析截图并生成回复

```bash
python examples/screenshot_analysis_client.py \
    --image screenshots/wechat.png \
    --mode reply \
    --intimacy 60 \
    --language zh-CN
```

**输出**:
```
================================================================================
💬 生成的回复
================================================================================

好啊！什么时候方便？我这周末都有空。

📊 元数据:
   模型: qwen-plus
   成本: $0.0020
```

### 示例3: 保存结果到文件

```bash
python examples/screenshot_analysis_client.py \
    --image screenshots/wechat.png \
    --mode reply \
    --output result.json
```

## 🔧 核心代码示例

### Python代码示例

```python
import asyncio
import httpx

async def analyze_screenshot(image_url: str):
    """分析截图的最简示例"""
    
    # API配置
    server_url = "http://localhost:8000"
    endpoint = f"{server_url}/api/v1/chat_screenshot/parse"
    
    # 构造请求
    request_data = {
        "image_url": image_url,
        "session_id": "my-session",
        "options": {
            "need_nickname": True,
            "need_sender": True,
            "force_two_columns": True
        }
    }
    
    # 发送请求
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(endpoint, json=request_data)
        result = response.json()
        
        if result["code"] == 0:
            # 分析成功
            data = result["data"]
            bubbles = data["bubbles"]
            
            print(f"识别到 {len(bubbles)} 条消息:")
            for bubble in bubbles:
                print(f"  [{bubble['sender']}] {bubble['text']}")
        else:
            # 分析失败
            print(f"错误: {result['msg']}")

# 运行
asyncio.run(analyze_screenshot("https://example.com/screenshot.png"))
```

### cURL示例

```bash
# 分析截图
curl -X POST http://localhost:8000/api/v1/chat_screenshot/parse \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/screenshot.png",
    "session_id": "test-001",
    "options": {
      "need_nickname": true,
      "need_sender": true,
      "force_two_columns": true
    }
  }'
```

## 📊 完整流程图

```
┌─────────────────────┐
│  本地图片文件        │
│  screenshot.png     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  上传到云存储        │
│  (S3, OSS等)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  获取图片URL         │
│  https://...        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  调用Parse API      │
│  POST /parse        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  获取分析结果        │
│  {bubbles, layout}  │
└──────────┬──────────┘
           │
           ├─────────────────┐
           │                 │
           ▼                 ▼
    ┌──────────┐      ┌──────────┐
    │ 只输出   │      │ 继续生成 │
    │ 分析结果 │      │ 回复     │
    └──────────┘      └─────┬────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ 转换为dialogs │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ 调用Generate │
                     │ Reply API    │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ 获取生成回复 │
                     └──────────────┘
```

## 🎯 使用场景

### 场景1: 聊天机器人集成

```python
# 用户上传截图 → 分析 → 生成回复 → 返回给用户
async def handle_screenshot_upload(image_file):
    # 1. 上传图片
    image_url = await upload_to_cloud(image_file)
    
    # 2. 分析截图
    analysis = await analyze_screenshot(image_url)
    
    # 3. 生成回复
    reply = await generate_reply(analysis)
    
    return reply
```

### 场景2: 批量处理

```python
# 批量分析多张截图
async def batch_analyze(image_paths: list[str]):
    tasks = []
    for path in image_paths:
        url = await upload_image(path)
        task = analyze_screenshot(url)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    return results
```

### 场景3: 数据标注

```python
# 分析截图用于数据标注
async def annotate_screenshots(image_dir: str):
    for image_path in Path(image_dir).glob("*.png"):
        # 分析
        result = await analyze_screenshot(image_path)
        
        # 保存标注
        save_annotation(image_path, result)
```

## 🔑 关键特性

### 1. 支持的聊天应用

- ✅ WeChat (微信)
- ✅ WhatsApp
- ✅ LINE
- ✅ 其他标准两列布局应用

### 2. 提取的信息

- 📷 图片尺寸
- 👥 参与者信息（昵称、ID）
- 💬 对话内容（文本、发送者、位置）
- 📐 布局信息（列数、角色映射）
- 📊 置信度分数

### 3. 输出格式

- JSON格式
- 兼容GenerateReplyRequest
- 支持保存到文件

## ⚙️ 配置选项

### 分析选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `need_nickname` | bool | true | 是否提取昵称 |
| `need_sender` | bool | true | 是否判断发送者 |
| `force_two_columns` | bool | true | 是否强制两列布局 |

### 生成选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `intimacy_value` | int | 50 | 亲密度 (0-100) |
| `language` | string | zh-CN | 回复语言 |
| `quality` | string | normal | 生成质量 |

## 🐛 错误处理

### 错误码说明

| 错误码 | 说明 | 解决方法 |
|--------|------|----------|
| 1001 | 图片下载失败 | 检查URL有效性 |
| 1002 | LLM调用失败 | 检查API密钥，重试 |
| 1003 | JSON解析失败 | 重试请求 |
| 1004 | 缺少必需字段 | 重试请求 |

### 错误处理示例

```python
try:
    result = await analyze_screenshot(image_url)
    
    if result["code"] != 0:
        # 处理业务错误
        print(f"分析失败: {result['msg']}")
        
        if result["code"] == 1001:
            # 图片问题
            print("请检查图片URL")
        elif result["code"] == 1002:
            # LLM问题
            print("LLM服务暂时不可用，请稍后重试")
            
except httpx.HTTPError as e:
    # 处理网络错误
    print(f"网络错误: {e}")
```

## 📚 更多资源

- [详细使用文档](SCREENSHOT_CLIENT_USAGE.md)
- [API文档](../README.md)
- [集成示例](screenshot_to_reply_example.py)

## 💡 最佳实践

1. **图片上传**: 使用云存储服务（S3, OSS）
2. **错误重试**: 实现指数退避重试机制
3. **超时设置**: 设置合理的超时时间（60-120秒）
4. **并发控制**: 批量处理时控制并发数
5. **成本监控**: 记录每次调用的成本
6. **日志记录**: 记录session_id用于追踪

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License
