# ✅ Prompt 版本管理系统设置完成

## 完成时间
2024-01-21

## 系统概述

已成功实现一个完整的 prompt 版本管理系统，包括：

### 核心功能
- ✅ **版本追踪** - 所有 prompt 变更都有记录
- ✅ **元数据管理** - 存储版本信息、作者、token 估算
- ✅ **回滚功能** - 一键切换到任何历史版本
- ✅ **对比分析** - 比较不同版本的差异和性能
- ✅ **CLI 工具** - 命令行管理界面
- ✅ **Git 集成** - 所有数据以文本文件存储，Git 友好

---

## 文件结构

### 新增文件

```
app/services/
├── prompt_manager.py          # Prompt 管理核心类

scripts/
├── init_prompt_versions.py    # 初始化脚本
└── manage_prompts.py           # CLI 管理工具

prompts/                        # Prompt 存储目录
├── registry.json               # 版本注册表
├── versions/                   # 所有版本
│   ├── scenario_analysis_v1.0-original.txt
│   ├── scenario_analysis_v2.0-compact.txt
│   ├── context_summary_v1.0-original.txt
│   ├── context_summary_v2.0-compact.txt
│   ├── reply_generation_v1.0-original.txt
│   ├── reply_generation_v2.0-compact.txt
│   ├── trait_discovery_v1.0-original.txt
│   └── trait_mapping_v1.0-original.txt
├── metadata/                   # 版本元数据
│   ├── scenario_analysis_v1.0-original.json
│   └── ...
└── active/                     # 当前激活版本
    ├── scenario_analysis.txt
    ├── context_summary.txt
    ├── reply_generation.txt
    ├── trait_discovery.txt
    └── trait_mapping.txt

文档/
├── PROMPT_VERSION_MANAGEMENT.md  # 使用指南
└── PROMPT_MANAGEMENT_SETUP_COMPLETE.md  # 本文档
```

---

## 已注册的版本

### Scenario Analysis（场景分析）
- **v1.0-original** - 496 tokens
  - 完整的策略描述
  - 包含所有策略分类说明
  
- **v2.0-compact** - 350 tokens ✓ ACTIVE
  - 只保留策略代码
  - 使用对话摘要
  - **减少 29%**

### Context Summary（上下文总结）
- **v1.0-original** - 489 tokens
  - 完整对话历史
  - 详细格式化
  
- **v2.0-compact** - 350 tokens ✓ ACTIVE
  - 最近 5 条消息
  - 精简格式
  - **减少 28%**

### Reply Generation（回复生成）
- **v1.0-original** - 832 tokens
  - 完整用户画像
  - 详细的 trait 描述
  - 完整对话历史
  
- **v2.0-compact** - 450 tokens ✓ ACTIVE
  - 精简用户画像
  - 只保留关键 traits
  - 只传递最后一条消息
  - **减少 46%**

### Trait Discovery（特征发现）
- **v1.0-original** - 311 tokens ✓ ACTIVE
  - 用于学习用户特征

### Trait Mapping（特征映射）
- **v1.0-original** - 494 tokens ✓ ACTIVE
  - 映射到标准特征

---

## Token 节省总结

| 组件 | 原始 | 优化后 | 节省 |
|------|------|--------|------|
| Scenario Analysis | 496 | 350 | -29% |
| Context Summary | 489 | 350 | -28% |
| Reply Generation | 832 | 450 | -46% |
| **总计** | **1,817** | **1,150** | **-37%** |

**每次完整流程节省：667 tokens**

---

## 快速使用指南

### 查看当前激活的版本

```bash
python scripts/manage_prompts.py active
```

### 查看所有版本

```bash
python scripts/manage_prompts.py list
```

### 对比两个版本

```bash
python scripts/manage_prompts.py compare reply_generation v1.0-original v2.0-compact
```

### 切换版本

```bash
# 切换到完整版（用于调试）
python scripts/manage_prompts.py activate scenario_analysis v1.0-original

# 切换回精简版（用于生产）
python scripts/manage_prompts.py activate scenario_analysis v2.0-compact
```

### 回滚到之前的版本

```bash
python scripts/manage_prompts.py rollback context_summary v1.0-original
```

### 导出版本

```bash
python scripts/manage_prompts.py export reply_generation v2.0-compact output.txt
```

---

## 在代码中使用

### 方法 1：使用 Prompt Manager（推荐）

```python
from app.services.prompt_manager import get_prompt_manager, PromptType

# 获取管理器
manager = get_prompt_manager()

# 获取当前激活的 prompt
prompt = manager.get_active_prompt(PromptType.SCENARIO_ANALYSIS)

# 使用 prompt
formatted_prompt = prompt.format(conversation_summary=summary)
```

### 方法 2：直接读取文件

```python
from pathlib import Path

# 读取激活的 prompt
prompt_file = Path("prompts/active/scenario_analysis.txt")
with open(prompt_file, 'r', encoding='utf-8') as f:
    prompt = f.read()
```

### 方法 3：集成到服务

```python
# 在 __init__ 中初始化
from app.services.prompt_manager import get_prompt_manager, PromptType

class SceneAnalyzer:
    def __init__(self, llm_adapter):
        self._llm_adapter = llm_adapter
        self._prompt_manager = get_prompt_manager()
    
    async def analyze_scene(self, input):
        # 获取当前激活的 prompt
        prompt_template = self._prompt_manager.get_active_prompt(
            PromptType.SCENARIO_ANALYSIS
        )
        
        # 使用 prompt
        prompt = prompt_template.format(...)
        # ...
```

---

## 版本管理工作流

### 日常开发

```bash
# 1. 查看当前版本
python scripts/manage_prompts.py active

# 2. 如需调试，切换到完整版
python scripts/manage_prompts.py activate reply_generation v1.0-original

# 3. 调试完成后，切换回精简版
python scripts/manage_prompts.py activate reply_generation v2.0-compact
```

### 添加新版本

```python
# 1. 在代码中定义新 prompt
NEW_PROMPT = """..."""

# 2. 注册新版本
from app.services.prompt_manager import get_prompt_manager, PromptType, PromptVersion

manager = get_prompt_manager()
manager.register_prompt(
    prompt_type=PromptType.SCENARIO_ANALYSIS,
    version=PromptVersion.V2_1_OPTIMIZED,  # 需要先在 PromptVersion 枚举中添加
    content=NEW_PROMPT,
    author="your_name",
    description="Further optimized version",
    tags=["optimized", "v2.1"],
    token_estimate=320,
    performance_notes="Additional 10% reduction"
)

# 3. 激活新版本
manager.activate_version(
    PromptType.SCENARIO_ANALYSIS,
    PromptVersion.V2_1_OPTIMIZED
)
```

### A/B 测试

```python
# 为不同用户组使用不同版本
def get_prompt_for_user(user_id: str):
    manager = get_prompt_manager()
    
    if hash(user_id) % 2 == 0:
        # Group A: Compact
        return manager.get_prompt_version(
            PromptType.REPLY_GENERATION,
            PromptVersion.V2_COMPACT
        )
    else:
        # Group B: Original
        return manager.get_prompt_version(
            PromptType.REPLY_GENERATION,
            PromptVersion.V1_ORIGINAL
        )
```

---

## Git 集成

### 提交 Prompt 变更

```bash
# 添加所有 prompt 文件
git add prompts/

# 提交变更
git commit -m "feat: add v2.0-compact prompts with 37% token reduction"

# 推送到远程
git push
```

### 查看 Prompt 历史

```bash
# 查看特定 prompt 的历史
git log prompts/versions/reply_generation_v2.0-compact.txt

# 查看变更内容
git diff HEAD~1 prompts/versions/reply_generation_v2.0-compact.txt
```

### 回滚 Prompt 变更

```bash
# 回滚到之前的 commit
git checkout HEAD~1 prompts/

# 或使用 prompt manager 回滚
python scripts/manage_prompts.py rollback reply_generation v1.0-original
```

---

## 监控和分析

### 查看版本历史

```python
from app.services.prompt_manager import get_prompt_manager

manager = get_prompt_manager()

# 查看所有变更历史
history = manager.registry["version_history"]
for event in history:
    print(f"{event['timestamp']}: {event['action']} - {event['prompt_id']}")
```

### Token 使用趋势

```python
# 分析 token 趋势
versions = manager.list_versions(PromptType.REPLY_GENERATION)

for v in sorted(versions, key=lambda x: x['created_at']):
    print(f"{v['version']}: {v['token_estimate']} tokens")
```

---

## 最佳实践

### ✅ DO（推荐）

1. **使用语义化版本号**
   - v1.0-original, v2.0-compact, v2.1-optimized

2. **记录详细元数据**
   - 描述、token 估算、性能观察

3. **测试后再激活**
   - 先在测试环境验证
   - 确认质量无下降

4. **保留回滚能力**
   - 不要删除旧版本
   - 随时可以回滚

5. **定期审查**
   - 检查 token 使用趋势
   - 优化低效的 prompts

### ❌ DON'T（避免）

1. **不要直接修改激活的文件**
   - 使用版本管理系统

2. **不要跳过测试**
   - 新版本必须验证

3. **不要忘记记录变更**
   - 填写描述和性能观察

4. **不要删除版本历史**
   - 保留所有版本用于对比

---

## 故障排除

### 问题 1：找不到 prompts 目录

```bash
# 重新初始化
python scripts/init_prompt_versions.py
```

### 问题 2：版本激活失败

```bash
# 检查版本是否存在
python scripts/manage_prompts.py list

# 确保版本名称正确
python scripts/manage_prompts.py activate scenario_analysis v2.0-compact
```

### 问题 3：无法导入 PromptManager

```python
# 确保项目根目录在 Python 路径中
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

---

## 下一步计划

### 短期（本周）
- [ ] 在所有服务中集成 Prompt Manager
- [ ] 运行 A/B 测试对比版本效果
- [ ] 收集实际 token 使用数据

### 中期（本月）
- [ ] 添加自动化测试
- [ ] 实现 prompt 性能监控
- [ ] 创建 prompt 优化指南

### 长期（持续）
- [ ] 探索更激进的优化策略
- [ ] 实现智能 prompt 选择
- [ ] 开发 prompt 质量评分系统

---

## 相关文档

- `PROMPT_VERSION_MANAGEMENT.md` - 详细使用指南
- `TOKEN_OPTIMIZATION_ANALYSIS.md` - Token 优化分析
- `TOKEN_OPTIMIZATION_IMPLEMENTATION.md` - 优化实施文档
- `VERIFICATION_GUIDE.md` - 验证指南

---

## 总结

✅ **已完成**
- Prompt 版本管理系统
- CLI 管理工具
- 版本注册和激活
- 对比和回滚功能
- Git 集成

🎯 **效果**
- 37% token 减少
- 完整的版本追踪
- 灵活的切换能力
- Git 友好的存储

📊 **下一步**
- 集成到服务中
- 运行 A/B 测试
- 持续优化

---

**系统已就绪，可以开始使用！** 🚀
