# Prompt 版本管理系统

## 概述

一个轻量级、基于文件的 prompt 版本管理系统，提供：

- ✅ **版本追踪** - 记录所有 prompt 变更历史
- ✅ **元数据管理** - 存储版本信息、作者、token 估算等
- ✅ **回滚功能** - 快速切换到任何历史版本
- ✅ **对比分析** - 比较不同版本的差异
- ✅ **Git 友好** - 所有数据以文本文件存储
- ✅ **CLI 工具** - 命令行管理界面

## 快速开始

### 1. 初始化版本管理

```bash
# 注册所有现有 prompts
python scripts/init_prompt_versions.py
```

这将创建 `prompts/` 目录结构：

```
prompts/
├── registry.json          # 版本注册表
├── versions/              # 所有版本的 prompt 文件
│   ├── scenario_analysis_v1.0-original.txt
│   ├── scenario_analysis_v2.0-compact.txt
│   └── ...
├── metadata/              # 版本元数据
│   ├── scenario_analysis_v1.0-original.json
│   └── ...
└── active/                # 当前激活的版本
    ├── scenario_analysis.txt
    ├── context_summary.txt
    └── reply_generation.txt
```

### 2. 查看所有版本

```bash
python scripts/manage_prompts.py list
```

输出示例：
```
SCENARIO_ANALYSIS
Status  Version           Tokens  Created     Description
------  ----------------  ------  ----------  ----------------------------------
✓       v2.0-compact      350     2024-01-20  Compact version with strategy codes
        v1.0-original     496     2024-01-20  Original with full descriptions
```

### 3. 查看当前激活的版本

```bash
python scripts/manage_prompts.py active
```

### 4. 切换版本

```bash
# 切换到完整版（用于调试）
python scripts/manage_prompts.py activate scenario_analysis v1.0-original

# 切换回精简版（用于生产）
python scripts/manage_prompts.py activate scenario_analysis v2.0-compact
```

### 5. 对比版本

```bash
python scripts/manage_prompts.py compare reply_generation v1.0-original v2.0-compact
```

输出示例：
```
Version 1: v1.0-original
  Length:         3591 chars
  Token Estimate: 832 tokens
  Created:        2024-01-20

Version 2: v2.0-compact
  Length:         1500 chars
  Token Estimate: 450 tokens
  Created:        2024-01-20

Difference:
  Length Change:  -2091 chars (-58.2%)
  Token Change:   -382 tokens
```

### 6. 导出版本

```bash
python scripts/manage_prompts.py export reply_generation v2.0-compact exported_prompt.txt
```

### 7. 回滚到之前的版本

```bash
python scripts/manage_prompts.py rollback context_summary v1.0-original
```

---

## 在代码中使用

### 方法 1：使用 Prompt Manager（推荐）

```python
from app.services.prompt_manager import get_prompt_manager, PromptType

# 获取管理器实例
manager = get_prompt_manager()

# 获取当前激活的 prompt
prompt = manager.get_active_prompt(PromptType.SCENARIO_ANALYSIS)

# 使用 prompt
llm_call = LLMCall(
    task_type="scene",
    prompt=prompt.format(conversation=conversation_text),
    quality="normal"
)
```

### 方法 2：直接读取激活的文件

```python
from pathlib import Path

# 读取当前激活的 prompt
prompt_file = Path("prompts/active/scenario_analysis.txt")
with open(prompt_file, 'r', encoding='utf-8') as f:
    prompt = f.read()
```

### 方法 3：集成到现有服务

更新服务以使用 prompt manager：

```python
# app/services/scene_analyzer_impl.py

from app.services.prompt_manager import get_prompt_manager, PromptType

class SceneAnalyzer(BaseSceneAnalyzer):
    def __init__(self, llm_adapter: BaseLLMAdapter):
        self._llm_adapter = llm_adapter
        self._prompt_manager = get_prompt_manager()
    
    async def analyze_scene(self, input: SceneAnalysisInput) -> SceneAnalysisResult:
        # 获取当前激活的 prompt
        prompt_template = self._prompt_manager.get_active_prompt(
            PromptType.SCENARIO_ANALYSIS
        )
        
        # 格式化并使用
        prompt = prompt_template.format(conversation_summary=input.current_conversation_summary)
        # ...
```

---

## 版本命名规范

### 版本号格式

`v{major}.{minor}-{label}`

- **major**: 主版本号（重大变更）
- **minor**: 次版本号（小改进）
- **label**: 版本标签（描述性）

### 示例

- `v1.0-original` - 原始版本
- `v2.0-compact` - 精简版本
- `v2.1-optimized` - 优化版本
- `v3.0-multilingual` - 多语言版本

---

## Prompt 类型

系统支持以下 prompt 类型：

| 类型 | 说明 | 当前激活版本 |
|------|------|--------------|
| `scenario_analysis` | 场景分析 | v2.0-compact |
| `context_summary` | 上下文总结 | v2.0-compact |
| `reply_generation` | 回复生成 | v2.0-compact |
| `trait_discovery` | 特征发现 | v1.0-original |
| `trait_mapping` | 特征映射 | v1.0-original |

---

## 添加新版本

### 步骤 1：创建新的 prompt 内容

```python
# 在 app/services/prompt_en.py 或新文件中定义
NEW_SCENARIO_PROMPT = """
Your new optimized prompt here...
"""
```

### 步骤 2：注册新版本

```python
from app.services.prompt_manager import get_prompt_manager, PromptType, PromptVersion

manager = get_prompt_manager()

# 添加新版本枚举（在 prompt_manager.py 中）
class PromptVersion(Enum):
    V1_ORIGINAL = "v1.0-original"
    V2_COMPACT = "v2.0-compact"
    V2_1_OPTIMIZED = "v2.1-optimized"  # 新增

# 注册新版本
manager.register_prompt(
    prompt_type=PromptType.SCENARIO_ANALYSIS,
    version=PromptVersion.V2_1_OPTIMIZED,
    content=NEW_SCENARIO_PROMPT,
    author="your_name",
    description="Further optimized with better structure",
    tags=["optimized", "v2.1"],
    token_estimate=320,
    performance_notes="10% additional token reduction",
    parent_version="scenario_analysis_v2.0-compact"
)
```

### 步骤 3：激活新版本

```bash
python scripts/manage_prompts.py activate scenario_analysis v2.1-optimized
```

---

## A/B 测试

### 设置 A/B 测试

```python
from app.services.prompt_manager import get_prompt_manager, PromptType, PromptVersion
import random

manager = get_prompt_manager()

def get_prompt_for_ab_test(user_id: str) -> str:
    """Get prompt based on A/B test assignment"""
    
    # 50/50 split
    if hash(user_id) % 2 == 0:
        # Group A: Compact version
        version = PromptVersion.V2_COMPACT
    else:
        # Group B: Original version
        version = PromptVersion.V1_ORIGINAL
    
    return manager.get_prompt_version(
        PromptType.REPLY_GENERATION,
        version
    )
```

### 收集测试数据

```python
# 记录使用的版本和结果
test_results = {
    "user_id": user_id,
    "version": version.value,
    "token_count": result.input_tokens + result.output_tokens,
    "quality_score": quality_score,
    "timestamp": datetime.now().isoformat()
}

# 保存到数据库或文件
```

---

## 最佳实践

### 1. 版本命名

- ✅ 使用语义化版本号
- ✅ 添加描述性标签
- ✅ 记录父版本关系

### 2. 元数据管理

- ✅ 填写详细的描述
- ✅ 估算 token 数量
- ✅ 记录性能观察

### 3. 测试流程

```bash
# 1. 注册新版本
python scripts/init_prompt_versions.py

# 2. 对比新旧版本
python scripts/manage_prompts.py compare scenario_analysis v1.0-original v2.0-compact

# 3. 在测试环境激活
python scripts/manage_prompts.py activate scenario_analysis v2.0-compact

# 4. 运行测试
python test_token_optimization.py

# 5. 如果有问题，立即回滚
python scripts/manage_prompts.py rollback scenario_analysis v1.0-original
```

### 4. Git 集成

```bash
# 提交 prompt 变更
git add prompts/
git commit -m "feat: add v2.1-optimized scenario analysis prompt"

# 查看 prompt 历史
git log prompts/versions/scenario_analysis_v2.0-compact.txt

# 回滚到之前的 commit
git checkout HEAD~1 prompts/
```

---

## 监控和分析

### 查看版本历史

```python
from app.services.prompt_manager import get_prompt_manager

manager = get_prompt_manager()

# 查看所有版本
versions = manager.list_versions()

# 查看特定类型的版本
scenario_versions = manager.list_versions(PromptType.SCENARIO_ANALYSIS)

# 查看版本历史
history = manager.registry["version_history"]
for event in history:
    print(f"{event['timestamp']}: {event['action']} - {event['prompt_id']}")
```

### Token 使用趋势

```python
# 分析 token 使用趋势
versions = manager.list_versions(PromptType.REPLY_GENERATION)

for v in sorted(versions, key=lambda x: x['created_at']):
    print(f"{v['version']}: {v['token_estimate']} tokens")
```

---

## 故障排除

### 问题 1：找不到 prompts 目录

**解决方案：**
```bash
# 重新初始化
python scripts/init_prompt_versions.py
```

### 问题 2：版本激活失败

**解决方案：**
```bash
# 检查版本是否存在
python scripts/manage_prompts.py list

# 确保版本名称正确
python scripts/manage_prompts.py activate scenario_analysis v2.0-compact
```

### 问题 3：无法导入 PromptManager

**解决方案：**
```python
# 确保项目根目录在 Python 路径中
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

---

## 高级功能

### 自定义 Prompt Manager

```python
from app.services.prompt_manager import PromptManager

# 使用自定义目录
custom_manager = PromptManager(prompts_dir="custom_prompts")

# 注册自定义 prompt
custom_manager.register_prompt(...)
```

### 批量操作

```python
# 批量激活特定版本
for prompt_type in [PromptType.SCENARIO_ANALYSIS, PromptType.CONTEXT_SUMMARY]:
    manager.activate_version(prompt_type, PromptVersion.V2_COMPACT)
```

### 导出所有版本

```bash
# 导出所有激活的版本
for type in scenario_analysis context_summary reply_generation; do
    python scripts/manage_prompts.py export $type v2.0-compact exports/${type}_v2.0.txt
done
```

---

## 相关文档

- `TOKEN_OPTIMIZATION_ANALYSIS.md` - Token 优化分析
- `TOKEN_OPTIMIZATION_IMPLEMENTATION.md` - 优化实施文档
- `VERIFICATION_GUIDE.md` - 验证指南

---

## 支持

如有问题或建议：
1. 查看 `prompts/registry.json` 了解当前状态
2. 运行 `python scripts/manage_prompts.py list` 查看所有版本
3. 检查 `prompts/metadata/` 目录中的元数据文件
