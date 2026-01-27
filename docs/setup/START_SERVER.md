# 如何启动服务器

> ✅ **服务器状态**: 服务器已成功配置所有必需的依赖项，包括截图解析API。所有依赖注入问题已解决。

## 快速启动

### 方式1: 使用 uvicorn 直接启动（推荐）

```bash
# Windows PowerShell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 或者使用简化命令
uvicorn app.main:app --reload
```

### 方式2: 使用 Python 模块方式启动

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 启动参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--host` | 监听地址 | 127.0.0.1 |
| `--port` | 监听端口 | 8000 |
| `--reload` | 代码变更自动重载（开发模式） | False |
| `--workers` | 工作进程数（生产模式） | 1 |

## 启动成功标志

看到以下输出表示启动成功：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using StatReload
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## 验证服务器运行

### 1. 访问健康检查端点

```bash
# 使用 curl
curl http://localhost:8000/health

# 或在浏览器中访问
http://localhost:8000/health
```

应该返回：
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

### 2. 访问 API 文档

在浏览器中打开：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 可用的 API 端点

启动服务器后，以下端点可用：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/v1/generate_reply` | POST | 生成回复 |
| `/api/v1/chat_screenshot/parse` | POST | 解析截图 |
| `/api/v1/context/build` | POST | 构建上下文 |
| `/api/v1/user_profile/*` | * | 用户画像相关 |

## 测试 Screenshot API

启动服务器后，可以使用客户端测试：

```bash
# 使用完整客户端
python examples/screenshot_analysis_client.py \
    --image path/to/screenshot.png \
    --mode analyze

# 使用简单示例
python examples/simple_screenshot_client.py
```

## 环境配置

### 1. 检查环境变量

确保已配置必要的环境变量（在 `.env` 文件中）：

```bash
# LLM API 配置
DASHSCOPE_API_KEY=your_api_key_here
OPENAI_API_KEY=your_openai_key_here

# 数据库配置（如果需要）
DATABASE_URL=sqlite:///./conversation.db

# 其他配置
DEBUG=true
LOG_LEVEL=INFO
```

### 2. 安装依赖

```bash
# 使用 pip
pip install -r requirements.txt

# 或使用 uv（推荐）
uv pip install -r requirements.txt
```

## 常见问题

### Q1: 端口被占用

**错误信息**:
```
ERROR:    [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000): 通常每个套接字地址(协议/网络地址/端口)只允许使用一次。
```

**解决方法**:
```bash
# 方法1: 使用其他端口
uvicorn app.main:app --port 8001

# 方法2: 查找并关闭占用端口的进程
# Windows
netstat -ano | findstr :8000
taskkill /PID <进程ID> /F

# Linux/Mac
lsof -i :8000
kill -9 <进程ID>
```

### Q2: 模块导入错误

**错误信息**:
```
ModuleNotFoundError: No module named 'app'
```

**解决方法**:
```bash
# 确保在项目根目录运行
cd /path/to/chatcoach

# 确保已安装依赖
pip install -r requirements.txt
```

### Q3: 数据库连接错误

**错误信息**:
```
ERROR: Could not connect to database
```

**解决方法**:
```bash
# 检查数据库文件是否存在
ls conversation.db

# 如果不存在，会自动创建
# 确保有写入权限
```

### Q4: API Key 未配置

**错误信息**:
```
ERROR: DASHSCOPE_API_KEY not found
```

**解决方法**:
```bash
# 创建 .env 文件
cp .env.example .env

# 编辑 .env 文件，添加你的 API Key
# DASHSCOPE_API_KEY=your_key_here
```

## 生产环境部署

### 使用 Gunicorn + Uvicorn Workers

```bash
# 安装 gunicorn
pip install gunicorn

# 启动（4个worker进程）
gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120
```

### 使用 Docker

```bash
# 构建镜像
docker build -t chatcoach-api .

# 运行容器
docker run -d \
    -p 8000:8000 \
    -e DASHSCOPE_API_KEY=your_key \
    --name chatcoach-api \
    chatcoach-api
```

## 停止服务器

### 开发模式
按 `Ctrl+C` 停止服务器

### 生产模式
```bash
# 查找进程
ps aux | grep uvicorn

# 停止进程
kill <进程ID>

# 或使用 pkill
pkill -f "uvicorn app.main:app"
```

## 日志查看

### 开发模式
日志直接输出到控制台

### 生产模式
```bash
# 重定向日志到文件
uvicorn app.main:app --log-config logging.conf > app.log 2>&1 &

# 查看日志
tail -f app.log
```

## 性能监控

### 查看进程状态
```bash
# 查看CPU和内存使用
top -p <进程ID>

# 或使用 htop
htop -p <进程ID>
```

### 查看请求统计
访问 http://localhost:8000/docs 查看 API 文档和测试接口

## 更多帮助

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Uvicorn 文档](https://www.uvicorn.org/)
- [项目 README](README.md)
