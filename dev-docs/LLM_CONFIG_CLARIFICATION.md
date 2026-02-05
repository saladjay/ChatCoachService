# LLM 配置说明

## 配置文件位置

系统中存在两个 LLM 配置位置：

### 1. `app/core/config.py` - 应用配置（Fallback）

```python
class LLMConfig(BaseSettings):
    default_provider: str = "openrouter"
    default_model: str = "google/gemini-2.0-flash-lite-001"
    fallback_model: str = "google/gemini-2.0-flash-lite-001"
    cheap_model: str = "google/gemini-2.0-flash-lite-001"
    premium_model: str = "google/gemini-2.0-flash-lite-001"
```

**用途**: 
- 这些是 **fallback 值**，仅在无法加载实际配置时使用
- 主要用于显示和日志记录
- **不是实际使用的配置**

### 2. `core/llm_adapter/config.yaml` - 实际 LLM 配置

```yaml
llm:
  default_provider: openrouter

providers:
  openrouter:
    api_key: ${OPENROUTER_API_KEY}
    base_url: ${OPENROUTER_BASE_URL}
    models:
      cheap: google/gemini-2.0-flash-lite-001
      normal: google/gemini-2.0-flash-lite-001
      premium: google/gemini-2.0-flash-lite-001
      multimodal: qwen/qwen3-vl-30b-a3b-instruct
```

**用途**:
- 这是 **实际使用的配置**
- LLMAdapter 在运行时加载此配置
- 支持环境变量替换（`${VAR_NAME}`）
- 包含所有 provider 的详细配置

## 为什么有两个配置？

### 历史原因

1. **`app/core/config.py`** 是应用层配置，使用 Pydantic Settings
2. **`core/llm_adapter/config.yaml`** 是 LLM 适配器的配置，使用 YAML

### 设计考虑

- **分离关注点**: 应用配置和 LLM 适配器配置分离
- **灵活性**: LLM 适配器可以独立使用，不依赖应用配置
- **环境变量**: YAML 支持环境变量替换，更灵活

## 实际使用的配置

**重要**: 系统实际使用的是 `core/llm_adapter/config.yaml` 中的配置！

### 配置优先级

```
core/llm_adapter/config.yaml (实际使用)
    ↓
环境变量 (${OPENROUTER_API_KEY})
    ↓
app/core/config.py (fallback，仅用于显示)
```

## 如何修改配置

### 方式 1: 修改 config.yaml（推荐）

```bash
# 编辑配置文件
vim core/llm_adapter/config.yaml

# 修改 default_provider
llm:
  default_provider: gemini  # 改为 gemini

# 修改模型
providers:
  openrouter:
    models:
      cheap: google/gemini-2.0-flash-lite-001
      normal: anthropic/claude-3.5-sonnet
      premium: anthropic/claude-3-opus
```

### 方式 2: 使用环境变量

```bash
# 设置 API Key
export OPENROUTER_API_KEY=sk-or-v1-xxx
export OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# 设置 multimodal provider
export MULTIMODAL_DEFAULT_PROVIDER=gemini
```

### 方式 3: 修改 .env 文件

```ini
# .env
OPENROUTER_API_KEY=sk-or-v1-xxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
MULTIMODAL_DEFAULT_PROVIDER=gemini
```

## 查看实际配置

### 方式 1: 运行 load_test.py

```bash
python tests/load_test.py --help
```

输出会显示：
```
================================================================================
LOAD TEST CONFIGURATION
================================================================================

Application Configuration:
  Default Provider:    openrouter (fallback)
  Default Model:       google/gemini-2.0-flash-lite-001 (fallback)

Actual LLM Configuration (from core/llm_adapter/config.yaml):
  Default Provider:    openrouter
  Cheap Model:         google/gemini-2.0-flash-lite-001
  Normal Model:        google/gemini-2.0-flash-lite-001
  Premium Model:       google/gemini-2.0-flash-lite-001
  Multimodal Model:    qwen/qwen3-vl-30b-a3b-instruct
================================================================================
```

### 方式 2: 查看配置文件

```bash
# 查看实际配置
cat core/llm_adapter/config.yaml

# 查看 fallback 配置
grep -A 10 "class LLMConfig" app/core/config.py
```

### 方式 3: Python 代码

```python
from pathlib import Path
import sys

# 加载 LLM adapter 配置
llm_adapter_path = Path("core/llm_adapter")
sys.path.insert(0, str(llm_adapter_path))

from llm_adapter import ConfigManager

config_manager = ConfigManager("core/llm_adapter/config.yaml")
default_provider = config_manager.get_default_provider()
provider_config = config_manager.get_provider_config(default_provider)

print(f"Default Provider: {default_provider}")
print(f"Cheap Model: {provider_config.models.cheap}")
print(f"Normal Model: {provider_config.models.normal}")
print(f"Premium Model: {provider_config.models.premium}")
print(f"Multimodal Model: {provider_config.models.multimodal}")
```

## 常见问题

### Q1: 为什么 `settings.llm.default_model` 和实际使用的模型不一致？

**A**: 因为 `settings.llm` 只是 fallback 值，实际使用的是 `config.yaml` 中的配置。

### Q2: 我应该修改哪个配置文件？

**A**: 修改 `core/llm_adapter/config.yaml`，这是实际使用的配置。

### Q3: 如何验证配置是否生效？

**A**: 
1. 运行 `python tests/load_test.py --help` 查看配置
2. 查看日志中的 provider 和 model 信息
3. 检查 trace 日志中的 LLM 调用记录

### Q4: 为什么不统一配置？

**A**: 
- LLM adapter 是独立模块，可以在其他项目中使用
- YAML 配置更灵活，支持环境变量和复杂结构
- 保持向后兼容性

## 最佳实践

### 1. 配置管理

```bash
# 开发环境
cp core/llm_adapter/config.yaml core/llm_adapter/config.dev.yaml
# 修改 config.dev.yaml

# 生产环境
cp core/llm_adapter/config.yaml core/llm_adapter/config.prod.yaml
# 修改 config.prod.yaml

# 使用环境变量指定配置文件
export LLM_CONFIG_PATH=core/llm_adapter/config.prod.yaml
```

### 2. 环境变量优先

```bash
# 使用环境变量覆盖配置
export OPENROUTER_API_KEY=sk-or-v1-xxx
export MULTIMODAL_DEFAULT_PROVIDER=gemini

# 这样可以在不修改配置文件的情况下切换配置
```

### 3. 验证配置

```bash
# 启动前验证配置
python -c "
from pathlib import Path
import sys
sys.path.insert(0, 'core/llm_adapter')
from llm_adapter import ConfigManager
cm = ConfigManager('core/llm_adapter/config.yaml')
print('Config loaded successfully')
print(f'Default provider: {cm.get_default_provider()}')
"
```

## 总结

| 配置文件 | 用途 | 优先级 | 修改建议 |
|---------|------|--------|---------|
| `core/llm_adapter/config.yaml` | 实际使用 | 高 | ✅ 修改此文件 |
| 环境变量 | 覆盖配置 | 最高 | ✅ 推荐使用 |
| `app/core/config.py` | Fallback | 低 | ❌ 不要修改 |

**记住**: 
- ✅ 修改 `core/llm_adapter/config.yaml`
- ✅ 使用环境变量覆盖
- ❌ 不要依赖 `app/core/config.py` 中的值

---

**更新日期**: 2026-02-05
**版本**: v1.0
