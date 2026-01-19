# 故障排除指南

本文档记录了运行示例时可能遇到的问题及其解决方案。

## 已修复的问题

### 1. SQLAlchemy 类型注解错误

**错误信息:**
```
NameError: Could not locate name MappedList in module app.db.models
```

**原因:** `app/db/models.py` 中使用了不存在的 `MappedList` 类型。

**解决方案:** 
- 导入 `Dict` 类型：`from typing import Any, Dict`
- 将 `MappedList[Dict[str, Any]]` 改为 `Mapped[list[Dict[str, Any]]]`

**修复文件:** `app/db/models.py`

### 2. UserProfileService 缺少 LLM Adapter

**错误信息:**
```
ValueError: LLM adapter not configured, cannot analyze scenario with LLM
```

**原因:** `UserProfileService` 需要 LLM adapter 才能进行场景分析，但在 `ServiceContainer` 中创建时没有传递。

**解决方案:** 
在 `app/core/container.py` 的 `_create_user_profile_service` 方法中传递 `llm_adapter` 参数：

```python
def _create_user_profile_service(self) -> BaseUserProfileService:
    llm_adapter = self.get("llm_adapter") if self.has("llm_adapter") else self._create_llm_adapter()
    return UserProfileService(llm_adapter=llm_adapter)
```

**修复文件:** `app/core/container.py`

### 3. Prompt 常量访问错误

**错误信息:**
```
AttributeError: 'UserProfileService' object has no attribute 'SCENARIO_ANALYSIS_PROMPT'
```

**原因:** 代码使用 `self.SCENARIO_ANALYSIS_PROMPT` 访问模块级常量。

**解决方案:** 
将 `self.SCENARIO_ANALYSIS_PROMPT` 改为 `SCENARIO_ANALYSIS_PROMPT`（直接使用模块级常量）。

**修复文件:** `app/services/user_profile.py`

## 运行示例

### 快速开始

1. **激活虚拟环境:**
   ```bash
   .venv/Scripts/activate.ps1  # Windows PowerShell
   # 或
   source .venv/bin/activate    # Linux/Mac
   ```

2. **测试环境配置:**
   ```bash
   python test_setup.py
   ```

3. **运行完整示例:**
   ```bash
   python examples/complete_flow_example.py
   ```

### Mock 模式 vs Real 模式

#### Mock 模式（推荐用于测试）

- **优点:** 不需要配置真实的 LLM API 密钥
- **用途:** 快速测试、开发、演示
- **配置:** 在代码中使用 `ServiceMode.MOCK`

```python
container = ServiceContainer(mode=ServiceMode.MOCK)
```

#### Real 模式（需要 API 密钥）

- **优点:** 使用真实的 LLM 进行场景分析和回复生成
- **用途:** 生产环境、真实测试
- **配置:** 
  1. 在代码中使用 `ServiceMode.REAL`
  2. 配置 `core/llm_adapter/config.yaml` 中的 API 密钥

```python
container = ServiceContainer(mode=ServiceMode.REAL)
```

## 常见问题

### Q: ModuleNotFoundError: No module named 'app'

**解决方法:** 确保从项目根目录运行脚本。

```bash
# 正确 ✓
cd /path/to/chatcoach
python examples/complete_flow_example.py

# 错误 ✗
cd /path/to/chatcoach/examples
python complete_flow_example.py
```

### Q: 如何切换到真实 LLM API？

**步骤:**

1. 修改 `examples/complete_flow_example.py`：
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
       models:
         low: "qwen-turbo"
         medium: "qwen-plus"
         high: "qwen-max"
   ```

3. 在示例中启用 LLM 分析：
   ```python
   # 步骤 4: 分析对话场景
   profile = await user_profile_service.analyze_scenario(
       user_id=user_id,
       conversation_id=conversation_id,
       messages=messages,
       use_llm=True,  # 改为 True
       provider="dashscope",
       model="qwen-plus"
   )
   ```

### Q: 数据库错误

**解决方法:** 数据库会自动创建。如果有问题，删除 `conversation.db` 文件重试。

```bash
rm conversation.db  # Linux/Mac
del conversation.db  # Windows
```

### Q: 如何查看详细日志？

**解决方法:** 在示例代码开头设置日志级别：

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## 测试清单

运行以下命令确保一切正常：

- [ ] `python test_setup.py` - 环境配置测试
- [ ] `python examples/complete_flow_example.py` - 完整流程示例（Mock 模式）
- [ ] `python run_example.py mock` - Mock 模式示例
- [ ] `python run_example.py simple` - 简化示例

## 获取帮助

如果遇到其他问题：

1. 查看 [QUICKSTART.md](QUICKSTART.md) - 快速启动指南
2. 查看 [examples/README.md](examples/README.md) - 示例文档
3. 查看设计文档 [.kiro/specs/conversation-generation-service/design.md](.kiro/specs/conversation-generation-service/design.md)

## 修复历史

- **2025-01-17**: 修复 SQLAlchemy MappedList 类型错误
- **2025-01-17**: 修复 UserProfileService LLM adapter 配置
- **2025-01-17**: 修复 Prompt 常量访问错误
- **2025-01-17**: 调整示例使用 Mock 模式避免需要 API 密钥
