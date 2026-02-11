# Vertex AI Gemini 配置指南

## 问题诊断

你遇到的错误：
```
404 Publisher Model `projects/wingy-e87ee/locations/asia-southeast1/publishers/google/models/gemini-2.0-flash-lite-001` was not found
```

## 根本原因

1. **模型名称错误**：使用了 `gemini-2.0-flash-lite-001`（带版本号），应该使用 `gemini-2.0-flash-lite`
2. **网络连接问题**：Vertex AI SDK 使用 gRPC 协议，无法连接到 Google Cloud（IP: 142.250.73.74:443）
3. **免费 API 配额已用完**：HTTP 模式使用免费 Gemini API，配额为 0

## 解决方案

### 1. 已修复的配置

已更新 `core/llm_adapter/config.yaml`：
- ✅ 模型名称改为 `gemini-2.0-flash-lite`（无版本号）
- ✅ 使用 Vertex AI 模式（付费层，更高配额）
- ✅ 设置了正确的项目 ID 和区域

### 2. 环境变量配置

已在 `.env` 文件中添加：
```bash
GOOGLE_APPLICATION_CREDENTIALS=core/llm_adapter/wingy-gemini-caller-e87ee-0e97104c6c62.json
```

### 3. 网络连接问题

**问题**：Vertex AI SDK 无法连接到 Google Cloud

**可能的解决方案**：

#### 方案 A：使用 VPN 或代理（推荐）

如果你的网络环境需要代理访问 Google Cloud：

1. 启动你的 VPN 或代理服务
2. 设置环境变量（在 `.env` 中取消注释）：
   ```bash
   HTTP_PROXY=http://proxy.zhizitech.org:10803
   HTTPS_PROXY=http://proxy.zhizitech.org:10803
   GRPC_PROXY=http://proxy.zhizitech.org:10803
   ```

3. 或者在 PowerShell 中临时设置：
   ```powershell
   $env:HTTP_PROXY="http://proxy.zhizitech.org:10803"
   $env:HTTPS_PROXY="http://proxy.zhizitech.org:10803"
   $env:GRPC_PROXY="http://proxy.zhizitech.org:10803"
   ```

#### 方案 B：使用 OpenRouter（备选）

如果 Vertex AI 连接问题无法解决，可以继续使用 OpenRouter：

在 `core/llm_adapter/config.yaml` 中：
```yaml
llm:
  default_provider: openrouter  # 使用 OpenRouter 作为默认
```

OpenRouter 提供 Gemini 模型访问，且不需要直接连接 Google Cloud。

### 4. 测试配置

运行测试脚本：
```bash
python scripts/test_vertex_ai.py
```

**预期结果**：
- ✅ 如果网络正常：成功调用 Vertex AI
- ❌ 如果网络被阻：503 连接错误（需要配置代理/VPN）

## 当前配置状态

### core/llm_adapter/config.yaml
```yaml
gemini:
  api_key: AIzaSyD2QJpLm36fthlDDVebQsgr-4ddnAoD1Dg
  mode: vertex
  project_id: wingy-e87ee
  location: asia-southeast1
  models:
    cheap: gemini-2.0-flash-lite      # ✅ 正确（无版本号）
    normal: gemini-2.0-flash-lite
    premium: gemini-2.0-flash
    multimodal: gemini-2.0-flash
```

### .env
```bash
GOOGLE_APPLICATION_CREDENTIALS=core/llm_adapter/wingy-gemini-caller-e87ee-0e97104c6c62.json
```

## 下一步

1. **如果你有 VPN/代理**：
   - 启动 VPN 或代理
   - 设置代理环境变量
   - 重启服务器
   - 测试连接

2. **如果无法访问 Google Cloud**：
   - 使用 OpenRouter 作为备选方案
   - OpenRouter 已配置好，可以直接使用

3. **验证配置**：
   ```bash
   python scripts/test_vertex_ai.py
   ```

## 常见错误

### 错误 1：404 Model not found
- **原因**：模型名称包含版本号 `-001`
- **解决**：使用稳定别名（如 `gemini-2.0-flash-lite`）

### 错误 2：503 Connection failed
- **原因**：无法连接到 Google Cloud
- **解决**：配置代理或使用 VPN

### 错误 3：429 Quota exceeded (free tier)
- **原因**：使用 HTTP 模式（免费 API）配额已用完
- **解决**：切换到 Vertex AI 模式（付费层）

### 错误 4：403 Permission denied
- **原因**：服务账号权限不足
- **解决**：在 GCP 控制台为服务账号添加 "Vertex AI User" 角色

## 参考链接

- [Vertex AI 模型版本文档](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions)
- [Vertex AI 区域可用性](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations)
- [Gemini API 配额限制](https://ai.google.dev/gemini-api/docs/rate-limits)
