# 401 Unauthorized 错误排查指南

## 错误特征

### 日志中的错误信息

```
HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 401 Unauthorized"
ValueError: Both calls failed or returned invalid data for merge_step
RuntimeError: merge_step analysis failed: Both calls failed or returned invalid data for merge_step
OrchestrationError: An error occurred during merge_step analysis
HTTPException: 500: merge_step analysis failed: An error occurred during merge_step analysis
```

### 错误流程

```
1. predict() 调用 get_merge_step_analysis_result()
2. get_merge_step_analysis_result() 调用 orchestrator.merge_step_analysis()
3. orchestrator.merge_step_analysis() 调用 _race_multimodal_calls()
4. _race_multimodal_calls() 同时调用两个 LLM:
   - Multimodal: mistralai/ministral-3b-2512 (OpenRouter)
   - Premium: google/gemini-2.0-flash-001 (OpenRouter)
5. 两个调用都返回 401 Unauthorized
6. _race_multimodal_calls() 抛出 ValueError: "Both calls failed"
7. 错误向上传播，最终返回 500 错误给客户端
```

## 根本原因

OpenRouter API key 无效或过期，导致所有通过 OpenRouter 的 LLM 调用失败。

由于 race strategy 同时使用两个模型，且两个都配置为使用 OpenRouter，所以当 API key 失效时，两个调用都失败。

## 诊断步骤

### 1. 确认是 401 错误

查看日志中是否有：

```bash
grep "401 Unauthorized" logs/server.log
```

如果有输出，确认是 API key 问题。

### 2. 检查当前 Provider

```bash
grep "LLM_DEFAULT_PROVIDER" .env
```

如果是 `openrouter`，需要切换或更新 API key。

### 3. 检查 API Key

```bash
# 查看 API key（部分隐藏）
grep "OPENROUTER_API_KEY" .env | sed 's/=.*/=***/'

# 测试 API key
python scripts/check_api_keys.py
```

### 4. 查看可用的 Provider

```bash
# 检查其他 provider 的 API key
grep "_API_KEY" .env | grep -v "^#"
```

## 快速修复

### 方案 1：切换到 DashScope（最快）

```bash
# 自动切换
bash scripts/switch_to_dashscope.sh

# 或手动切换
vim .env
# 修改: LLM_DEFAULT_PROVIDER=dashscope

# 重启服务
pkill -f "uvicorn app.main:app"
./start_server.sh
```

### 方案 2：切换到 Vertex AI (Gemini)

```bash
# 编辑 .env
vim .env
# 修改: LLM_DEFAULT_PROVIDER=gemini

# 确保凭证文件存在
ls -la core/llm_adapter/wingy-gemini-caller-e87ee-0e97104c6c62.json

# 重启服务
pkill -f "uvicorn app.main:app"
./start_server.sh
```

### 方案 3：更新 OpenRouter API Key

```bash
# 编辑 .env
vim .env
# 修改: OPENROUTER_API_KEY=sk-or-v1-你的新key

# 重启服务
pkill -f "uvicorn app.main:app"
./start_server.sh
```

## 验证修复

### 1. 检查服务启动日志

```bash
tail -f logs/server.log
```

应该看到：

```
INFO - Starting application...
INFO - LLM adapter initialized with provider: dashscope
INFO - Available models: cheap=qwen-turbo, normal=qwen-turbo, premium=qwen-turbo, multimodal=qwen3-vl-30b-a3b-instruct
```

### 2. 发送测试请求

```bash
curl -X POST http://localhost:8000/api/v1/ChatAnalysis/predict \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "session_id": "test_'$(date +%s)'",
    "content": ["https://test-r2.zhizitech.org/test35.jpg"],
    "language": "en",
    "scene": 1,
    "sign": "test"
  }'
```

### 3. 检查响应

成功响应应该包含：

```json
{
  "success": true,
  "message": "成功",
  "results": [
    {
      "content": "https://...",
      "dialogs": [...],
      "scenario": "{...}"
    }
  ]
}
```

### 4. 检查日志中的成功信息

```bash
tail -100 logs/server.log | grep -i "merge_step\|multimodal\|premium"
```

应该看到：

```
INFO - Starting merge_step race: multimodal vs premium
INFO - merge_step multimodal completed in XXXXms (model: qwen3-vl-30b-a3b-instruct)
INFO - merge_step: multimodal result is valid
INFO - Using multimodal result for immediate response
```

## 常见问题

### Q1: 切换 provider 后仍然报 401

**可能原因：**
- 服务未重启
- 新 provider 的 API key 也无效
- 配置文件未保存

**解决方案：**

```bash
# 1. 确认配置已保存
cat .env | grep LLM_DEFAULT_PROVIDER

# 2. 强制重启服务
pkill -9 -f "uvicorn app.main:app"
sleep 2
./start_server.sh

# 3. 测试新 provider 的 API key
python scripts/check_api_keys.py
```

### Q2: DashScope 返回其他错误

**检查 DashScope 配置：**

```bash
# 查看配置
grep -A 10 "dashscope:" core/llm_adapter/config.yaml

# 测试 API key
python scripts/check_api_keys.py
```

**常见 DashScope 错误：**

- `InvalidParameter`: 模型名称错误或参数不支持
- `Throttling`: 请求频率过高
- `InsufficientBalance`: 账户余额不足

### Q3: 所有 provider 都失败

**检查网络连接：**

```bash
# 测试 OpenRouter
curl -I https://openrouter.ai/api/v1/models

# 测试 DashScope
curl -I https://dashscope.aliyuncs.com

# 测试 Google Cloud
curl -I https://aiplatform.googleapis.com
```

**检查代理设置：**

```bash
# 查看代理配置
grep -i proxy .env
grep -i proxy core/llm_adapter/config.yaml

# 如果需要代理
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
```

## 预防措施

### 1. 配置多个 Provider 作为备份

在 `core/llm_adapter/config.yaml` 中配置多个 provider：

```yaml
llm:
  default_provider: dashscope  # 主要
  
providers:
  dashscope:
    api_key: ${DASHSCOPE_API_KEY}
    # ...
  
  gemini:
    api_key: ${GOOGLE_APPLICATION_CREDENTIALS}
    # ... (作为备份)
  
  openrouter:
    api_key: ${OPENROUTER_API_KEY}
    # ... (作为备份)
```

### 2. 定期检查 API Key 状态

添加到 crontab：

```bash
# 每 6 小时检查一次
0 */6 * * * cd /path/to/chatcoachservice && python scripts/check_api_keys.py >> logs/api_key_check.log 2>&1
```

### 3. 监控 401 错误

在日志中监控 401 错误：

```bash
# 实时监控
tail -f logs/server.log | grep --color=always "401\|Unauthorized"

# 统计 401 错误数量
grep "401 Unauthorized" logs/server.log | wc -l
```

### 4. 设置告警

当检测到 401 错误时发送告警：

```python
# 在 app/api/v1/middleware.py 中添加
import smtplib
from email.mime.text import MIMEText

def send_alert(message):
    msg = MIMEText(message)
    msg['Subject'] = 'API Key Alert'
    msg['From'] = 'alert@example.com'
    msg['To'] = 'admin@example.com'
    
    s = smtplib.SMTP('localhost')
    s.send_message(msg)
    s.quit()

# 在错误处理中调用
if "401 Unauthorized" in error_message:
    send_alert(f"API key invalid: {error_message}")
```

## 相关文件

- `dev-docs/FIX_401_UNAUTHORIZED.md` - 快速修复指南
- `scripts/check_api_keys.py` - API key 检查脚本
- `scripts/switch_to_dashscope.sh` - 自动切换到 DashScope
- `scripts/switch_to_dashscope.ps1` - Windows 版本
- `core/llm_adapter/config.yaml` - LLM 配置
- `.env` - 环境变量

## 总结

**问题：** OpenRouter API key 无效导致 401 错误

**快速修复：**
```bash
bash scripts/switch_to_dashscope.sh
./start_server.sh
```

**验证：**
```bash
curl -X POST http://localhost:8000/api/v1/ChatAnalysis/predict ...
```

**预期结果：** 不再有 401 错误，merge_step 分析成功
