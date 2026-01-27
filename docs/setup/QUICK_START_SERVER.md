# 快速启动服务器指南

## 🚀 一键启动

### Windows (PowerShell)

```powershell
# 方式1: 直接启动（推荐）
uvicorn app.main:app --reload

# 方式2: 指定完整参数
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 方式3: 使用 Python 模块
python -m uvicorn app.main:app --reload
```

### Linux/Mac (Bash)

```bash
# 方式1: 直接启动（推荐）
uvicorn app.main:app --reload

# 方式2: 使用启动脚本
chmod +x start_server.sh
./start_server.sh
```

## ✅ 验证服务器启动成功

### 1. 查看控制台输出

看到以下信息表示启动成功：

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using StatReload
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 2. 测试健康检查端点

打开新的终端窗口，运行：

```bash
# Windows PowerShell
curl http://localhost:8000/health

# 或使用 Invoke-WebRequest
Invoke-WebRequest http://localhost:8000/health
```

应该返回：
```json
{"status":"healthy","version":"1.0.0"}
```

### 3. 访问 API 文档

在浏览器中打开：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📸 测试 Screenshot API

服务器启动后，打开**新的终端窗口**，运行：

```bash
# 测试分析截图
python examples/screenshot_analysis_client.py \
    --image D:\project\chatlayoutdet_ws\test_images\test_discord_2.png \
    --mode analyze
```

## 🔧 常见问题解决

### 问题1: uvicorn 命令未找到

**错误**:
```
uvicorn : 无法将"uvicorn"项识别为 cmdlet、函数、脚本文件或可运行程序的名称。
```

**解决**:
```bash
# 安装 uvicorn
pip install uvicorn

# 或使用 uv
uv pip install uvicorn
```

### 问题2: 端口 8000 被占用

**错误**:
```
ERROR: [Errno 10048] error while attempting to bind on address
```

**解决**:
```bash
# 使用其他端口
uvicorn app.main:app --port 8001 --reload

# 或查找并关闭占用端口的进程
netstat -ano | findstr :8000
taskkill /PID <进程ID> /F
```

### 问题3: 模块导入错误

**错误**:
```
ModuleNotFoundError: No module named 'app'
```

**解决**:
```bash
# 确保在项目根目录
cd D:\project\chatcoach

# 确保已安装所有依赖
pip install -r requirements.txt
```

### 问题4: Screenshot API 返回 404

**错误**:
```
404 Not Found for url 'http://localhost:8000/api/v1/chat_screenshot/parse'
```

**解决**:

这个问题已经修复！我已经在 `app/main.py` 中添加了 screenshot 路由注册。

重启服务器即可：
1. 按 `Ctrl+C` 停止当前服务器
2. 重新运行 `uvicorn app.main:app --reload`

## 📋 完整启动流程

### 第一次启动

```bash
# 1. 进入项目目录
cd D:\project\chatcoach

# 2. 确保虚拟环境已激活
# (chatcoach) 应该显示在命令提示符前

# 3. 安装/更新依赖
pip install -r requirements.txt

# 4. 配置环境变量（如果需要）
# 复制 .env.example 到 .env
# 编辑 .env 添加 API keys

# 5. 启动服务器
uvicorn app.main:app --reload
```

### 后续启动

```bash
# 1. 进入项目目录
cd D:\project\chatcoach

# 2. 激活虚拟环境（如果未激活）
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

# 3. 启动服务器
uvicorn app.main:app --reload
```

## 🎯 测试完整流程

### 终端1: 启动服务器

```bash
uvicorn app.main:app --reload
```

等待看到 "Application startup complete."

### 终端2: 测试 API

```bash
# 测试健康检查
curl http://localhost:8000/health

# 测试截图分析
python examples/screenshot_analysis_client.py \
    --image path/to/screenshot.png \
    --mode analyze

# 测试截图分析 + 生成回复
python examples/screenshot_analysis_client.py \
    --image path/to/screenshot.png \
    --mode reply \
    --intimacy 60
```

## 📊 可用的 API 端点

启动后可用的端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/docs` | GET | Swagger API 文档 |
| `/redoc` | GET | ReDoc API 文档 |
| `/api/v1/chat_screenshot/parse` | POST | 解析聊天截图 |
| `/api/v1/generate_reply` | POST | 生成回复 |
| `/api/v1/context/build` | POST | 构建上下文 |

## 🛑 停止服务器

在运行服务器的终端窗口中按 `Ctrl+C`

## 💡 开发提示

1. **使用 --reload 参数**: 代码修改后自动重启服务器
2. **查看日志**: 所有请求和错误都会显示在控制台
3. **使用 API 文档**: http://localhost:8000/docs 可以直接测试 API
4. **多终端工作**: 一个终端运行服务器，另一个终端测试客户端

## 📚 更多信息

- [完整启动文档](START_SERVER.md)
- [Screenshot 客户端使用](examples/SCREENSHOT_CLIENT_USAGE.md)
- [API 文档](README.md)
