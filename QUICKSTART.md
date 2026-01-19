# 快速启动指南

## 前提条件

- Python 3.10+
- 已安装依赖: `pip install -r requirements.txt` 或 `uv sync`
- 从项目根目录运行所有命令

## 1. 激活虚拟环境

```bash
# Windows PowerShell
.venv/Scripts/activate.ps1

# Linux/Mac
source .venv/bin/activate
```

## 2. 测试环境

```bash
python test_setup.py
```

如果看到 "✓ 所有测试通过！"，说明环境配置正确。

## 3. 运行示例

### 选项 A: Mock 模式（推荐，不需要 API 密钥）

**这是默认模式，开箱即用！**

```bash
python examples/complete_flow_example.py
```

Mock 模式特点：
- ✅ 不需要配置 API 密钥
- ✅ 快速测试和开发
- ✅ 演示完整流程
- ⚠️ 使用模拟数据，不调用真实 LLM

### 选项 B: 真实 API 模式

1. 修改 `examples/complete_flow_example.py` 中的模式：
   ```python
   # 将这行
   container = ServiceContainer(mode=ServiceMode.MOCK)
   # 改为
   container = ServiceContainer(mode=ServiceMode.REAL)
   ```

2. 配置 API 密钥（在 `core/llm_adapter/config.yaml`）：
   ```yaml
   providers:
     dashscope:
       api_key: "your-api-key-here"
   ```

3. 运行示例：
   ```bash
   python examples/complete_flow_example.py
   ```

### 选项 C: HTTP API 模式

终端 1 - 启动服务器：
```bash
uvicorn app.main:app --reload
```

终端 2 - 运行客户端：
```bash
python examples/api_client_example.py
```

## 3. 常见问题

### 虚拟环境未激活

**症状:** 找不到模块或命令

**解决方法:** 
```bash
# Windows PowerShell
.venv/Scripts/activate.ps1

# Linux/Mac
source .venv/bin/activate
```

### ModuleNotFoundError: No module named 'app'

**解决方法:** 确保从项目根目录运行脚本。

```bash
# 正确 ✓
cd /path/to/chatcoach
python examples/complete_flow_example.py

# 错误 ✗
cd /path/to/chatcoach/examples
python complete_flow_example.py
```

### 找不到 LLM API 配置

**解决方法:** 使用 Mock 模式，或配置 `core/llm_adapter/config.yaml`

### 数据库错误

**解决方法:** 数据库会自动创建。如果有问题，删除 `conversation.db` 文件重试。

```bash
# Windows
del conversation.db

# Linux/Mac
rm conversation.db
```

## 4. 故障排除

如果遇到问题，请查看 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) 获取详细的故障排除指南。

常见修复：
- SQLAlchemy 类型注解错误 ✅ 已修复
- UserProfileService LLM adapter 配置 ✅ 已修复
- Prompt 常量访问错误 ✅ 已修复

## 5. 下一步

- 查看 [examples/README.md](examples/README.md) 了解更多示例
- 查看 [.kiro/specs/](. kiro/specs/) 了解系统设计
- 访问 http://localhost:8000/docs 查看 API 文档（启动服务器后）

## 6. 项目结构

```
chatcoach/
├── app/                    # 主应用代码
│   ├── api/               # API 路由
│   ├── core/              # 核心配置和容器
│   ├── db/                # 数据库模型
│   ├── models/            # 数据模型
│   └── services/          # 业务服务
├── core/                   # 核心库
│   ├── llm_adapter/       # LLM 适配器
│   └── user_profile/      # 用户画像服务
├── examples/              # 示例代码
├── tests/                 # 测试代码
├── test_setup.py          # 环境测试脚本
└── QUICKSTART.md          # 本文件
```

## 7. 核心概念

### Orchestrator（编排器）
协调整个生成流程的中心服务。

### 生成流程
```
Context Builder → Scene Analyzer → Persona Inferencer 
    → Reply Generator → Intimacy Checker → 返回结果
```

### 服务模式
- **Mock 模式**: 使用模拟数据，不调用真实 API
- **Real 模式**: 使用真实的 LLM API 和服务

## 8. 获取帮助

- 查看示例代码中的注释
- 阅读 [examples/README.md](examples/README.md)
- 查看设计文档 [.kiro/specs/conversation-generation-service/design.md](.kiro/specs/conversation-generation-service/design.md)
