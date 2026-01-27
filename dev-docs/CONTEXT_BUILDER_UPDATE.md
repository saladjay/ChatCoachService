# ContextBuilder 更新说明

## 更新内容

将 `app/services/context_impl.py` 中的真实 `ContextBuilder` 实现集成到 `ServiceContainer` 中，替代 Mock 实现。

## 修改的文件

### 1. `app/services/context_impl.py`

**改进:**
- 完善了 `ContextBuilder` 类的实现
- 添加了 LLM 调用逻辑来分析对话历史
- 实现了 `_format_conversation` 方法来格式化对话消息
- 支持 Pydantic `Message` 对象和字典两种格式
- 添加了 JSON 解析和错误处理

**关键方法:**

```python
async def build_context(self, input: ContextBuilderInput) -> ContextResult:
    """使用 LLM 分析对话历史并构建上下文"""
    # 格式化对话历史
    conversation_text = self._format_conversation(input.history_dialog)
    
    # 构建 prompt
    prompt = CONTEXT_SUMMARY_PROMPT.format(conversation=conversation_text)
    
    # 调用 LLM
    llm_call = LLMCall(...)
    result = await self._llm_adapter.call(llm_call)
    
    # 解析结果
    analysis = json.loads(result.text)
    return ContextResult(...)
```

### 2. `app/core/container.py`

**改进:**
- 添加了 `ContextBuilder` 的导入
- 更新了 `_create_context_builder` 方法
- 在 REAL 模式下使用真实的 `ContextBuilder`
- 在 MOCK 模式下继续使用 `MockContextBuilder`

**关键代码:**

```python
def _create_context_builder(self) -> BaseContextBuilder:
    """Create context builder based on mode."""
    if self._mode == ServiceMode.MOCK:
        return MockContextBuilder()
    # Real implementation uses LLM Adapter
    llm_adapter = self.get("llm_adapter") if self.has("llm_adapter") else self._create_llm_adapter()
    return ContextBuilder(llm_adapter=llm_adapter)
```

### 3. 修复导入问题

**修复的文件:**
- `app/services/__init__.py`
- `app/core/container.py`
- `examples/complete_flow_example.py`
- `examples/userprofile_basic_example.py`
- `examples/qwen_userprofile_example.py`

**问题:** 文件名是 `user_profile_impl.py` 而不是 `user_profile.py`

**修复:** 将所有 `from app.services.user_profile import` 改为 `from app.services.user_profile_impl import`

## 功能说明

### Mock 模式

在 Mock 模式下，`ContextBuilder` 返回默认值，不调用真实的 LLM API：

```python
container = ServiceContainer(mode=ServiceMode.MOCK)
orchestrator = container.create_orchestrator()
```

**特点:**
- ✅ 不需要 API 密钥
- ✅ 快速测试
- ✅ 返回固定的模拟数据

### Real 模式

在 Real 模式下，`ContextBuilder` 使用 LLM 分析对话历史：

```python
container = ServiceContainer(mode=ServiceMode.REAL)
orchestrator = container.create_orchestrator()
```

**特点:**
- ✅ 使用真实的 LLM API
- ✅ 智能分析对话上下文
- ✅ 提取情绪状态和亲密度
- ⚠️ 需要配置 API 密钥

## 使用示例

### 基本使用

```python
from app.core.container import ServiceContainer, ServiceMode
from app.models.api import GenerateReplyRequest

# 创建服务容器（Real 模式）
container = ServiceContainer(mode=ServiceMode.REAL)
orchestrator = container.create_orchestrator()

# 创建请求
request = GenerateReplyRequest(
    user_id="user_001",
    target_id="target_001",
    conversation_id="conv_001",
    dialogs=[
        {"speaker": "user", "text": "你好"},
        {"speaker": "assistant", "text": "你好！有什么可以帮你的吗？"}
    ],
    quality="normal",
)

# 生成回复
response = await orchestrator.generate_reply(request)
print(response.reply_text)
```

### 直接使用 ContextBuilder

```python
from app.services.context_impl import ContextBuilder
from app.services.llm_adapter import create_llm_adapter
from app.models.schemas import ContextBuilderInput, Message

# 创建 LLM adapter
llm_adapter = create_llm_adapter()

# 创建 ContextBuilder
context_builder = ContextBuilder(llm_adapter=llm_adapter)

# 准备输入
messages = [
    Message(id="1", speaker="user", content="你好", timestamp=None),
    Message(id="2", speaker="assistant", content="你好！", timestamp=None),
]

input_data = ContextBuilderInput(
    user_id="user_001",
    target_id="target_001",
    conversation_id="conv_001",
    history_dialog=messages,
)

# 构建上下文
context = await context_builder.build_context(input_data)
print(f"对话摘要: {context.conversation_summary}")
print(f"情绪状态: {context.emotion_state}")
print(f"亲密度: {context.current_intimacy_level}")
```

## 测试结果

### 环境测试

```bash
python test_setup.py
```

**结果:** ✅ 所有测试通过

### 完整流程示例

```bash
python examples/complete_flow_example.py
```

**结果:** ✅ 成功运行

**输出:**
- ✓ 初始化服务容器
- ✓ 设置用户画像
- ✓ 准备对话历史
- ✓ 分析对话场景
- ✓ 生成回复
- ✓ 查看用户画像信息

## 技术细节

### ContextBuilder 架构

```
ContextBuilder
    ├── __init__(llm_adapter, provider, model)
    ├── build_context(input) -> ContextResult
    │   ├── _format_conversation(messages)
    │   ├── LLM 调用
    │   └── JSON 解析
    └── _format_conversation(messages) -> str
```

### 数据流

```
GenerateReplyRequest
    ↓
Orchestrator._build_context()
    ↓
ContextBuilder.build_context()
    ↓
_format_conversation() → 格式化对话
    ↓
LLM API 调用 → 分析上下文
    ↓
JSON 解析 → ContextResult
    ↓
返回给 Orchestrator
```

### 错误处理

1. **JSON 解析失败:** 返回默认值
2. **LLM 调用失败:** 抛出 `ContextBuildError`
3. **空对话历史:** 返回 "（暂无对话历史）"

## 配置要求

### Real 模式配置

1. **配置 LLM API 密钥** (`core/llm_adapter/config.yaml`):
   ```yaml
   providers:
     dashscope:
       api_key: "your-api-key-here"
       models:
         low: "qwen-turbo"
         medium: "qwen-plus"
         high: "qwen-max"
   ```

2. **设置环境变量** (可选):
   ```bash
   export LLM_DEFAULT_PROVIDER="dashscope"
   export LLM_DEFAULT_MODEL="qwen-plus"
   ```

## 下一步

- [ ] 添加更多的上下文分析维度
- [ ] 优化 prompt 模板
- [ ] 添加缓存机制
- [ ] 添加单元测试
- [ ] 性能优化

## 相关文档

- [QUICKSTART.md](QUICKSTART.md) - 快速启动指南
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - 故障排除指南
- [CHANGELOG.md](CHANGELOG.md) - 更新日志
- [examples/README.md](examples/README.md) - 示例文档

## 贡献者

- Kiro AI Assistant - 代码实现和文档编写
