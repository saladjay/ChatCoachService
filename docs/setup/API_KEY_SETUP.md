# API密钥配置说明

## ✅ 测试结果

Screenshot API已成功运行！测试返回：

```json
{
  "code": 1002,
  "msg": "LLM API call failed: No vision providers available. Please configure API keys.",
  "data": null
}
```

这个错误是**预期的**，因为还没有配置多模态LLM的API密钥。

## 需要配置的API密钥

Screenshot解析功能需要使用支持视觉的多模态LLM。你需要配置**至少一个**以下API密钥：

### 选项1: OpenAI (推荐)
- 模型: GPT-4o, GPT-4 Turbo, GPT-4 Vision
- 优点: 最稳定，结构化输出质量最好
- 获取密钥: https://platform.openai.com/api-keys

```env
OPENAI_API_KEY=sk-your-openai-key-here
```

### 选项2: Google Gemini
- 模型: Gemini 1.5 Pro, Gemini 1.5 Flash
- 优点: 成本较低，速度快
- 获取密钥: https://makersuite.google.com/app/apikey

```env
GOOGLE_API_KEY=your-google-api-key-here
```

### 选项3: Anthropic Claude
- 模型: Claude 3.5 Sonnet, Claude 3 Opus
- 优点: 高质量输出
- 获取密钥: https://console.anthropic.com/

```env
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
```

## 配置步骤

### 1. 编辑 .env 文件

在项目根目录的 `.env` 文件中添加你的API密钥：

```bash
# 在 .env 文件末尾添加（至少选择一个）
OPENAI_API_KEY=sk-your-key-here
# 或
GOOGLE_API_KEY=your-key-here
# 或
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 2. 重启服务器

配置完API密钥后，需要重启服务器：

```powershell
# 停止当前服务器 (Ctrl+C)
# 然后重新启动
.\start_server.ps1
```

### 3. 测试Screenshot API

重启后，再次运行测试：

```powershell
.\.venv\Scripts\activate.ps1; python test_screenshot_simple.py
```

如果配置正确，你应该会看到成功的解析结果（或者错误代码1003/1004，这表示LLM已经被调用但返回格式有问题）。

## 使用你的Discord截图测试

配置好API密钥后，你可以测试你的Discord截图：

```powershell
.\.venv\Scripts\activate.ps1; python examples/screenshot_analysis_client.py --image "D:/project/chatlayoutdet_ws/test_images/test_discord_2.png" --mode analyze --server http://localhost:8000
```

## 优先级顺序

如果配置了多个API密钥，系统会按以下优先级选择：

1. OpenAI (最高优先级)
2. Gemini
3. Claude

## 成本估算

每次screenshot解析的大致成本：

| 提供商 | 模型 | 估算成本 |
|--------|------|----------|
| OpenAI | GPT-4o | $0.01 - $0.03 |
| OpenAI | GPT-4 Turbo | $0.03 - $0.05 |
| Google | Gemini 1.5 Flash | $0.001 - $0.003 |
| Google | Gemini 1.5 Pro | $0.005 - $0.01 |
| Anthropic | Claude 3.5 Sonnet | $0.01 - $0.03 |

**推荐**: 如果预算有限，使用 Gemini 1.5 Flash（最便宜）或 GPT-4o（性价比最好）。

## 错误代码说明

- `1001`: 图片下载/处理失败 - 检查图片URL是否可访问
- `1002`: LLM调用失败 - **当前错误**，需要配置API密钥
- `1003`: LLM返回的JSON格式无效 - LLM已调用但返回格式有问题
- `1004`: LLM返回缺少必需字段 - LLM已调用但数据不完整

## 下一步

1. ✅ 服务器已成功启动
2. ✅ Screenshot API端点正常工作
3. ⏳ **当前步骤**: 配置API密钥
4. ⏳ 测试实际的Discord截图解析

配置好API密钥后，你就可以开始解析真实的聊天截图了！
