# Prompt 管理模式分析

## 问题

在执行 "how to reduce token" 计划前后，prompt 的存储位置和管理方式是什么？新的 compact prompt 是否受到现有管理模式的管理？

## 当前状态分析

### 1. 两套 Prompt 管理系统（并存但未统一）

#### 系统 A: `prompts/` 目录管理系统（旧系统）

**目录结构**:
```
prompts/
├── active/                    # 当前激活的 prompt
│   ├── context_summary.txt
│   ├── reply_generation.txt
│   ├── scenario_analysis.txt
│   ├── trait_discovery.txt
│   └── trait_mapping.txt
├── versions/                  # 版本历史
│   ├── context_summary_v1.0-original.txt
│   ├── context_summary_v2.0-compact.txt
│   ├── reply_generation_v1.0-original.txt
│   ├── reply_generation_v2.0-compact.txt
│   ├── scenario_analysis_v1.0-original.txt
│   └── scenario_analysis_v2.0-compact.txt
├── metadata/                  # 元数据
│   ├── context_summary_v1.0-original.json
│   ├── context_summary_v2.0-compact.json
│   └── ...
├── legacy/                    # 遗留代码
│   ├── prompt_en.py
│   ├── prompt_cn.py
│   └── README.md
└── registry.json             # 注册表
```

**特点**:
- 使用文件系统存储 prompt 文本
- 有版本管理（v1.0-original, v2.0-compact）
- 有元数据和注册表
- 有 `active/` 目录指向当前使用的版本

**管理工具**:
- `scripts/init_prompt_versions.py` - 初始化 prompt 版本
- `scripts/manage_prompts.py` - 管理 prompt（切换版本、查看历史等）
- `app/services/prompt_manager.py` - Prompt 管理器类

#### 系统 B: `app/services/prompt_compact.py`（新系统）

**位置**: `app/services/prompt_compact.py`

**特点**:
- 直接在 Python 代码中定义 prompt
- 使用 Python 字符串常量
- 有版本标识符（如 `[PROMPT:context_summary_compact_v1]`）
- 通过代码导入使用

**实际使用的 Prompt**:
```python
# 在 app/services/prompt_compact.py 中定义
CONTEXT_SUMMARY_PROMPT_COMPACT = """..."""
CONTEXT_SUMMARY_PROMPT_COMPACT_V2 = """..."""
SCENARIO_PROMPT_COMPACT = """..."""
SCENARIO_PROMPT_COMPACT_V2 = """..."""
CHATCOACH_PROMPT_COMPACT = """..."""
CHATCOACH_PROMPT_COMPACT_V2 = """..."""
```

### 2. 关键发现：两套系统未统一

#### 问题 1: 内容不一致

**prompts/versions/context_summary_v2.0-compact.txt**:
```
You are a conversation scenario analyst.

Conversation history:
{conversation}

Classify:
- Emotion: positive | neutral | negative
- Intimacy: stranger | familiar | intimate | recovery
- Scenario: SAFE | BALANCED | RISKY | RECOVERY | NEGATIVE

Output JSON only:
{
  "conversation_summary": "summary",
  "emotion_state": "positive|neutral|negative",
  "current_intimacy_level": "stranger|familiar|intimate|recovery",
  "scenario": "SAFE|BALANCED|RISKY|RECOVERY|NEGATIVE"
}
```

**app/services/prompt_compact.py 中的 CONTEXT_SUMMARY_PROMPT_COMPACT**:
```python
CONTEXT_SUMMARY_PROMPT_COMPACT = """
You are a conversation scenario analyst.

Conversation history:
{conversation}

Classify:
- Emotion: positive | neutral | negative
- Intimacy: stranger | familiar | intimate | recovery
- Scenario: SAFE | BALANCED | RISKY | RECOVERY | NEGATIVE

Output JSON only:
{
  "conversation_summary": "summary",
  "emotion_state": "positive|neutral|negative",
  "current_intimacy_level": "stranger|familiar|intimate|recovery",
  "scenario": "SAFE|BALANCED|RISKY|RECOVERY|NEGATIVE"
}
"""
```

**结论**: 这两个内容相同，但 `prompt_compact.py` 中还有更优化的 V2 版本（CONTEXT_SUMMARY_PROMPT_COMPACT_V2），而 `prompts/versions/` 中没有。

#### 问题 2: 实际使用的是哪个？

**代码中实际使用**:
```python
# app/services/context_impl.py
from app.services.prompt_compact import CONTEXT_SUMMARY_PROMPT_COMPACT

# 实际调用
prompt = f"[PROMPT:context_summary_compact_v1]\n{CONTEXT_SUMMARY_PROMPT_COMPACT.format(conversation=conversation_text)}"
```

**结论**: 实际使用的是 `app/services/prompt_compact.py` 中的定义，**不是** `prompts/versions/` 中的文件。

#### 问题 3: 版本标识符不匹配

**prompts/versions/** 中的版本命名:
- `context_summary_v1.0-original.txt`
- `context_summary_v2.0-compact.txt`

**prompt_compact.py** 中的版本标识符:
- `[PROMPT:context_summary_compact_v1]`
- `[PROMPT:scene_analyzer_compact_v2]`
- `[PROMPT:reply_generation_compact_v2_with_reasoning]`
- `[PROMPT:reply_generation_compact_v2_no_reasoning]`

**结论**: 版本命名规则不一致。

### 3. 实际执行流程

#### Token Reduction 前（旧系统）

```
prompts/versions/
├── context_summary_v1.0-original.txt  ← 原始 verbose prompt
└── scenario_analysis_v1.0-original.txt

↓ (通过 scripts/init_prompt_versions.py 初始化)

prompts/active/
├── context_summary.txt  ← 指向 v1.0-original
└── scenario_analysis.txt

↓ (但实际代码中使用的是)

app/services/prompt_en.py
├── CONTEXT_SUMMARY_PROMPT = """..."""  ← 硬编码在代码中
└── SCENARIO_PROMPT = """..."""
```

#### Token Reduction 后（新系统）

```
开发新的 compact prompt
↓
直接写入 app/services/prompt_compact.py
├── CONTEXT_SUMMARY_PROMPT_COMPACT = """..."""
├── CONTEXT_SUMMARY_PROMPT_COMPACT_V2 = """..."""
└── SCENARIO_PROMPT_COMPACT_V2 = """..."""

↓ (添加版本标识符)

在 prompt 前加上 [PROMPT:version_id]
例如: "[PROMPT:context_summary_compact_v1]\n{prompt}"

↓ (通过 logging_llm_adapter.py 记录)

logs/trace.jsonl
├── prompt_version: "context_summary_compact_v1"
└── prompt_version: "scene_analyzer_compact_v2"

↓ (但 prompts/versions/ 没有同步更新)

prompts/versions/
├── context_summary_v2.0-compact.txt  ← 旧的 compact 版本
└── 没有 V2、V3 等更新的版本
```

## 问题总结

### 1. 新的 compact prompt 在哪里？

**答案**: 在 `app/services/prompt_compact.py` 中，以 Python 代码形式存在。

**具体位置**:
- `CONTEXT_SUMMARY_PROMPT_COMPACT` - Context 分析 compact 版本
- `CONTEXT_SUMMARY_PROMPT_COMPACT_V2` - Context 分析 compact V2（更优化）
- `SCENARIO_PROMPT_COMPACT_V2` - 场景分析 compact V2
- `CHATCOACH_PROMPT_COMPACT_V2` - 回复生成 compact V2

### 2. 是否受目前的管理模式管理？

**答案**: **否**，新的 compact prompt 不受 `prompts/` 目录管理系统的管理。

**原因**:
1. 新 prompt 直接写在 Python 代码中（`prompt_compact.py`）
2. 没有同步到 `prompts/versions/` 目录
3. 没有更新 `prompts/registry.json`
4. 没有创建对应的 metadata 文件
5. `scripts/manage_prompts.py` 无法管理这些 prompt

### 3. 两套系统的关系

```
旧系统 (prompts/)          新系统 (prompt_compact.py)
     ↓                              ↓
  文件存储                       代码存储
     ↓                              ↓
  版本管理                       版本标识符
     ↓                              ↓
  管理工具                       直接导入
     ↓                              ↓
  未实际使用                     实际使用
```

## 建议的解决方案

### 方案 1: 统一到文件系统管理（推荐）

**优点**:
- 利用现有的管理工具
- 版本历史清晰
- 易于对比和回滚
- 非技术人员也能编辑

**实施步骤**:

1. **同步 prompt 到 prompts/versions/**:
```bash
# 创建新版本文件
prompts/versions/context_summary_v3.0-compact_v2.txt
prompts/versions/scenario_analysis_v3.0-compact_v2.txt
prompts/versions/reply_generation_v3.0-compact_v2_with_reasoning.txt
prompts/versions/reply_generation_v3.0-compact_v2_no_reasoning.txt
```

2. **更新 registry.json**:
```json
{
  "prompts": {
    "context_summary": [
      {"prompt_id": "context_summary_v1.0-original", "version": "v1.0-original"},
      {"prompt_id": "context_summary_v2.0-compact", "version": "v2.0-compact"},
      {"prompt_id": "context_summary_v3.0-compact_v2", "version": "v3.0-compact_v2"}
    ]
  }
}
```

3. **修改 prompt_compact.py 从文件加载**:
```python
from app.services.prompt_manager import PromptManager

prompt_manager = PromptManager()

# 从文件加载而不是硬编码
CONTEXT_SUMMARY_PROMPT_COMPACT = prompt_manager.get_prompt(
    "context_summary", 
    version="v3.0-compact_v2"
)
```

### 方案 2: 废弃文件系统，统一到代码管理

**优点**:
- 代码即文档
- 类型检查和 IDE 支持
- 更快的加载速度
- 版本控制通过 Git

**实施步骤**:

1. **删除或归档 prompts/ 目录**:
```bash
mv prompts/ prompts_archived/
```

2. **在 prompt_compact.py 中添加完整的版本历史**:
```python
# 保留历史版本用于对比
CONTEXT_SUMMARY_PROMPT_V1_ORIGINAL = """..."""
CONTEXT_SUMMARY_PROMPT_V2_COMPACT = """..."""
CONTEXT_SUMMARY_PROMPT_V3_COMPACT_V2 = """..."""

# 当前使用的版本
CONTEXT_SUMMARY_PROMPT = CONTEXT_SUMMARY_PROMPT_V3_COMPACT_V2
```

3. **使用 Git 管理版本历史**

### 方案 3: 混合管理（当前状态，不推荐）

**现状**:
- 文件系统存储历史版本（参考用）
- 代码中定义实际使用的版本
- 两者不同步

**问题**:
- 容易混淆
- 维护成本高
- 版本不一致

## 推荐行动计划

### 短期（立即执行）

1. **创建同步脚本**:
```python
# scripts/sync_prompts_to_files.py
"""将 prompt_compact.py 中的 prompt 同步到 prompts/versions/"""
```

2. **更新文档**:
- 在 `prompts/README.md` 中说明当前状态
- 标注哪些是实际使用的，哪些是历史参考

### 中期（1-2 周内）

3. **统一管理方式**:
- 选择方案 1 或方案 2
- 执行迁移
- 更新所有相关文档

4. **建立流程**:
- 新增 prompt 的标准流程
- 修改 prompt 的审批流程
- 版本发布的检查清单

### 长期（持续优化）

5. **自动化测试**:
- Prompt 变更的 A/B 测试
- Token 使用量监控
- 质量评估自动化

6. **版本管理增强**:
- 自动生成 changelog
- 版本对比工具
- 回滚机制

## 当前实际使用情况

### 实际生效的 Prompt（在代码中）

| Prompt | 位置 | 版本标识符 | 是否在 prompts/versions/ |
|--------|------|-----------|------------------------|
| Context Summary | `prompt_compact.py` | `context_summary_compact_v1` | ✅ 有旧版本 |
| Scene Analyzer | `prompt_compact.py` | `scene_analyzer_compact_v2` | ✅ 有旧版本 |
| Reply Generation (with reasoning) | `prompt_compact.py` | `reply_generation_compact_v2_with_reasoning` | ❌ 无 |
| Reply Generation (no reasoning) | `prompt_compact.py` | `reply_generation_compact_v2_no_reasoning` | ❌ 无 |
| Strategy Planner | `prompt_compact.py` | `strategy_planner_compact_v1` | ❌ 无 |
| Trait Discovery | `prompts/legacy/prompt_en.py` | 无 | ✅ 有 |
| Trait Mapping | `prompts/legacy/prompt_en.py` | 无 | ✅ 有 |

### 未使用的 Prompt（仅存档）

| Prompt | 位置 | 状态 |
|--------|------|------|
| Original verbose prompts | `prompts/versions/*v1.0-original.txt` | 仅参考 |
| Old compact prompts | `prompts/versions/*v2.0-compact.txt` | 已被代码中的版本替代 |
| Legacy Python prompts | `prompts/legacy/*.py` | 部分仍在使用（trait 相关） |

## 结论

**回答你的问题**:

1. **新的 compact prompt 在哪里？**
   - 在 `app/services/prompt_compact.py` 中，以 Python 代码形式存在

2. **是否受目前的管理模式管理？**
   - **否**，不受 `prompts/` 目录管理系统的管理
   - 新 prompt 直接在代码中定义和使用
   - 没有同步到文件系统的版本管理中

3. **两套系统的关系？**
   - 并存但未统一
   - 文件系统（`prompts/`）主要用于历史参考
   - 代码系统（`prompt_compact.py`）是实际使用的

**建议**: 选择一种管理方式并统一，推荐使用文件系统管理（方案 1），因为已有完整的工具链。

---

*最后更新: 2026-01-22*
*相关文档*:
- `PROMPT_CLEANUP_SUMMARY.md`
- `PROMPT_VERSION_MANAGEMENT.md`
- `prompts/legacy/README.md`


## 更新：已完成同步（2026-01-22）

### 执行的操作

1. **创建同步脚本**: `scripts/sync_prompts_to_files.py`
2. **同步所有 compact prompt 到文件系统**
3. **更新 registry.json 和 metadata**
4. **更新 active/ 目录指向最新版本**

### 同步后的状态

#### 新增的版本

| Prompt Type | 新版本 | Token 估算 | 说明 |
|-------------|--------|-----------|------|
| context_summary | v3.0-compact | 118 | 与 v2.0 相同 |
| context_summary | v3.1-compact_v2 | 70 | 压缩输出格式 |
| scenario_analysis | v3.0-compact | 417 | Compact 版本 |
| scenario_analysis | v3.1-compact_v2 | 376 | 压缩代码格式 |
| reply_generation | v3.0-compact | 146 | Compact 版本 |
| reply_generation | v3.1-compact_v2_with_reasoning | 133 | V2 带推理 |
| reply_generation | v3.2-compact_v2_no_reasoning | 133 | V2 无推理（最优化） |

#### 当前 Active 版本

```bash
$ python scripts/manage_prompts.py list

SCENARIO_ANALYSIS
  ✓ ACTIVE | v2.0-compact    | 350 tokens
           | v3.0-compact    | 417 tokens
           | v3.1-compact_v2 | 376 tokens

CONTEXT_SUMMARY
  ✓ ACTIVE | v2.0-compact    | 350 tokens
           | v3.0-compact    | 118 tokens
           | v3.1-compact_v2 | 70 tokens

REPLY_GENERATION
  ✓ ACTIVE | v2.0-compact                   | 450 tokens
           | v3.0-compact                   | 146 tokens
           | v3.1-compact_v2_with_reasoning | 133 tokens
           | v3.2-compact_v2_no_reasoning   | 133 tokens
```

### 现在的管理方式

#### 统一的管理流程

1. **开发新 Prompt**:
   - 在 `app/services/prompt_compact.py` 中定义
   - 添加版本标识符（如 `[PROMPT:version_id]`）

2. **同步到文件系统**:
   ```bash
   python scripts/sync_prompts_to_files.py
   ```

3. **使用管理工具**:
   ```bash
   # 列出所有版本
   python scripts/manage_prompts.py list
   
   # 查看特定版本
   python scripts/manage_prompts.py show context_summary v3.1-compact_v2
   
   # 对比两个版本
   python scripts/manage_prompts.py compare context_summary v2.0-compact v3.1-compact_v2
   ```

4. **切换版本**:
   ```bash
   python scripts/manage_prompts.py activate context_summary v3.1-compact_v2
   ```

### 两套系统现在的关系

```
代码定义 (prompt_compact.py)
    ↓
    | 1. 开发新 prompt
    ↓
同步脚本 (sync_prompts_to_files.py)
    ↓
    | 2. 同步到文件系统
    ↓
文件系统 (prompts/)
    ├── versions/     ← 所有版本
    ├── metadata/     ← 元数据
    ├── active/       ← 当前激活版本
    └── registry.json ← 注册表
    ↓
    | 3. 使用管理工具
    ↓
管理工具 (manage_prompts.py)
    ├── list          ← 列出版本
    ├── show          ← 查看内容
    ├── compare       ← 对比版本
    └── activate      ← 切换版本
```

### 优势

1. **代码优先**: 在代码中开发和测试 prompt
2. **版本管理**: 通过文件系统管理所有版本
3. **工具支持**: 使用现有工具进行管理
4. **Git 友好**: 所有变更都可以通过 Git 追踪
5. **易于对比**: 可以轻松对比不同版本的效果

### 下一步建议

1. **自动化同步**: 在 CI/CD 中自动运行同步脚本
2. **版本测试**: 为每个版本添加自动化测试
3. **性能监控**: 记录每个版本的实际 token 使用和质量指标
4. **文档生成**: 自动生成版本对比报告

### 相关命令

```bash
# 同步 prompt 到文件系统
python scripts/sync_prompts_to_files.py

# 列出所有 prompt 版本
python scripts/manage_prompts.py list

# 查看特定 prompt
python scripts/manage_prompts.py show context_summary v3.1-compact_v2

# 对比两个版本
python scripts/manage_prompts.py compare context_summary v2.0-compact v3.1-compact_v2

# 激活特定版本
python scripts/manage_prompts.py activate context_summary v3.1-compact_v2

# 运行版本对比示例
python -m examples.prompt_version_comparison
```

---

*同步完成时间: 2026-01-22*
*状态: 两套系统已统一*
