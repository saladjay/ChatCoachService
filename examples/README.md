# 示例代码说明

本目录包含了对话生成服务的完整使用示例。

## 文件列表

### 1. `complete_flow_example.py` - 完整流程示例

演示整个系统的完整使用流程，包括：

- ✅ 初始化服务容器和所有依赖
- ✅ 设置用户画像（显式标签）
- ✅ 准备对话历史数据
- ✅ 使用 LLM 分析对话场景
- ✅ 通过 Orchestrator 生成回复
- ✅ 查看用户画像的完整信息
- ✅ 从对话中学习用户偏好

**运行方式:**

```bash
# 方式 1: 从项目根目录运行
python examples/complete_flow_example.py

# 方式 2: 使用 Python 模块方式运行
python -m examples.complete_flow_example

# 或者使用 Mock 模式（不需要真实 API）
# 修改代码中的 ServiceMode.REAL 为 ServiceMode.MOCK
```

**注意:** 必须从项目根目录运行，或者确保项目根目录在 Python 路径中。

**包含的子示例:**

- `main()` - 完整流程演示
- `simple_example()` - 简化流程（最小化代码）
- `mock_example()` - Mock 模式演示（用于测试）

### 2. `api_client_example.py` - API 客户端示例

演示如何通过 HTTP API 调用服务：

- ✅ 调用生成回复 API
- ✅ 处理不同的响应状态码
- ✅ 测试健康检查端点
- ✅ 测试不同质量等级
- ✅ 测试验证错误

**运行方式:**

```bash
# 1. 启动服务器（从项目根目录）
uvicorn app.main:app --reload

# 2. 在另一个终端运行客户端（从项目根目录）
python examples/api_client_example.py
```

**注意:** 必须从项目根目录运行。

### 3. `qwen_userprofile_example.py` - 用户画像示例

演示如何使用用户画像服务：

- ✅ 创建和管理用户画像
- ✅ 设置显式标签
- ✅ 分析对话场景
- ✅ 学习用户偏好

### 4. `userprofile_basic_example.py` - 基础画像示例

演示用户画像的基础功能。

## 快速开始

### 步骤 0: 测试环境配置

首先运行环境测试脚本，确保一切配置正确：

```bash
# 从项目根目录运行
python test_setup.py
```

如果所有测试通过，你就可以运行示例了。

### 方式 1: 使用 Mock 模式（推荐用于测试）

不需要配置真实的 LLM API，适合快速测试和开发。

```python
from app.core.container import ServiceContainer, ServiceMode

# 创建 Mock 模式的服务容器
container = ServiceContainer(mode=ServiceMode.MOCK)
orchestrator = container.create_orchestrator()

# 创建请求
from app.models.api import GenerateReplyRequest

request = GenerateReplyRequest(
    user_id="user_001",
    target_id="target_001",
    conversation_id="conv_001",
    quality="normal",
)

# 生成回复（使用 Mock 数据）
response = await orchestrator.generate_reply(request)
print(response.reply_text)
```

### 方式 2: 使用真实 LLM API

需要配置 LLM API 密钥。

**配置步骤:**

1. 复制 `.env.example` 为 `.env`
2. 配置 LLM API 密钥（在 `core/llm_adapter/config.yaml` 中）
3. 运行示例

```python
from app.core.container import ServiceContainer, ServiceMode

# 创建 REAL 模式的服务容器
container = ServiceContainer(mode=ServiceMode.REAL)
orchestrator = container.create_orchestrator()

# 其余代码同上...
```

## 核心流程说明

### 完整的对话生成流程

```
用户请求
    ↓
[1. Context Builder] - 整合对话历史、情绪趋势等信息
    ↓
[2. Scene Analyzer] - 分析对话场景（破冰/推进/冷却/维持）
    ↓
[3. Persona Inferencer] - 推断用户画像（风格/节奏/风险容忍度）
    ↓
[4. Reply Generator] - 使用 LLM 生成回复
    ↓
[5. Intimacy Checker] - 检查回复是否适合当前关系阶段
    ↓
    ├─ 通过 → 返回回复
    └─ 不通过 → 重试（最多 3 次）→ 降级回复
```

### 服务依赖关系

```
Orchestrator
    ├── Context Builder (整合上下文)
    ├── Scene Analyzer (场景分析)
    ├── Persona Inferencer (画像推断)
    │   └── UserProfile Service (用户画像服务)
    │       └── LLM Adapter (用于场景分析)
    ├── Reply Generator (回复生成)
    │   └── LLM Adapter (调用 LLM)
    ├── Intimacy Checker (亲密度检查)
    └── Billing Service (计费服务)
```

## 配置说明

### 环境变量

在 `.env` 文件中配置：

```bash
# 应用配置
APP_NAME="Conversation Generation Service"
DEBUG=false

# 数据库配置
DB_URL="sqlite+aiosqlite:///./conversation.db"

# LLM 配置
LLM_DEFAULT_PROVIDER="openai"
LLM_DEFAULT_MODEL="gpt-4"

# Orchestrator 配置
ORCHESTRATOR_MAX_RETRIES=3
ORCHESTRATOR_TIMEOUT_SECONDS=30.0

# 计费配置
BILLING_COST_LIMIT_USD=0.1
BILLING_DEFAULT_USER_QUOTA_USD=10.0
```

### LLM 配置

在 `core/llm_adapter/config.yaml` 中配置 LLM 提供商：

```yaml
providers:
  dashscope:  # 通义千问
    api_key: "your-api-key"
    models:
      low: "qwen-turbo"
      medium: "qwen-plus"
      high: "qwen-max"
  
  openai:  # OpenAI
    api_key: "your-api-key"
    models:
      low: "gpt-3.5-turbo"
      medium: "gpt-4"
      high: "gpt-4-turbo"
```

## 常见问题

### Q: 如何切换 Mock 模式和 Real 模式？

A: 在创建 ServiceContainer 时指定 mode 参数：

```python
# Mock 模式
container = ServiceContainer(mode=ServiceMode.MOCK)

# Real 模式
container = ServiceContainer(mode=ServiceMode.REAL)
```

### Q: 如何指定使用特定的 LLM 提供商？

A: 使用 LLM Adapter 的 `call_with_provider` 方法：

```python
llm_adapter = container.get_llm_adapter()

result = await llm_adapter.call_with_provider(
    prompt="你好",
    provider="dashscope",  # 指定提供商
    model="qwen-plus",     # 指定模型
    user_id="user_001"
)
```

### Q: 如何查看生成过程的详细日志？

A: 配置日志级别：

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,  # 设置为 DEBUG 级别
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Q: 如何处理配额超限错误？

A: 捕获 `QuotaExceededError` 异常：

```python
from app.core.exceptions import QuotaExceededError

try:
    response = await orchestrator.generate_reply(request)
except QuotaExceededError as e:
    print(f"配额超限: {e.message}")
    # 处理配额超限逻辑
```

## 更多资源

- [API 文档](http://localhost:8000/docs) - 启动服务器后访问
- [设计文档](../.kiro/specs/conversation-generation-service/design.md)
- [需求文档](../.kiro/specs/conversation-generation-service/requirements.md)
- [任务列表](../.kiro/specs/conversation-generation-service/tasks.md)

## 贡献

欢迎提交 Issue 和 Pull Request！
