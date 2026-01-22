# Phase 3 Token Analysis Examples

这个目录包含用于分析和对比 Phase 3 优化效果的示例脚本。

---

## 快速开始

### 1. 运行完整分析示例

```bash
# 运行完整的 token 分析示例
python examples/phase3_token_analysis_example.py
```

这个脚本会：
- ✅ 使用 baseline 配置运行完整流程
- ✅ 使用 optimized 配置运行完整流程
- ✅ 生成两个 trace 文件（`logs/trace_baseline.jsonl` 和 `logs/trace_optimized.jsonl`）
- ✅ 自动分析和对比 token 使用情况
- ✅ 显示详细的 prompt 和 response 内容

### 2. 分析已有的 trace 文件

```bash
# 分析单个文件
python scripts/analyze_trace.py logs/trace.jsonl

# 对比两个文件
python scripts/analyze_trace.py logs/trace_baseline.jsonl logs/trace_optimized.jsonl --compare

# 显示详细信息（包含完整 prompt 和 response）
python scripts/analyze_trace.py logs/trace.jsonl --detailed
```

---

## 输出示例

### 对比报告示例

```
================================================================================
TOKEN USAGE COMPARISON REPORT
================================================================================

📊 OVERALL COMPARISON
--------------------------------------------------------------------------------
Metric                         Baseline        Optimized       Change         
--------------------------------------------------------------------------------
Total Tokens                   2,450           1,225           +50.0%
Input Tokens                   1,800           1,200           +33.3%
Output Tokens                  650             325             +50.0%
Number of LLM Calls            3               3               

📋 PER-CALL BREAKDOWN
--------------------------------------------------------------------------------

Call #1: scene
  Model: qwen-flash
  Input Tokens:    800 →    600 (+25.0%)
  Output Tokens:   150 →     75 (+50.0%)

Call #2: generation
  Model: qwen-flash
  Input Tokens:    900 →    500 (+44.4%)
  Output Tokens:   450 →    225 (+50.0%)
```

### 详细调用信息示例

```
================================================================================
LLM CALL #1: SCENE
================================================================================

📌 Metadata:
  Provider: dashscope
  Model: qwen-flash
  Timestamp: 2026-01-22T10:30:45.123456

📊 Token Usage:
  Input Tokens:    800
  Output Tokens:   150
  Total Tokens:    950
  Cost (USD):    $0.004750

📝 Prompt (Input):
--------------------------------------------------------------------------------
You are a conversation coach analyzing a dating conversation...
[完整的 prompt 内容]

💬 Response (Output):
--------------------------------------------------------------------------------
{"rs":"I","scn":"B","il":50,"rf":[],"cs":"S","rsc":"B","rst":["emotional_resonance"]}
```

---

## 配置选项

### Baseline 配置（未优化）

```python
PromptConfig(
    include_reasoning=True,      # 包含推理字段
    max_reply_tokens=200,        # 较长的回复
    use_compact_schemas=False    # 使用完整模式
)
```

### Optimized 配置（Phase 3 优化）

```python
PromptConfig(
    include_reasoning=False,     # 排除推理字段 → 节省 ~40% 输出 token
    max_reply_tokens=100,        # 适中的回复长度 → 节省 ~20% 输出 token
    use_compact_schemas=True     # 使用紧凑模式 → 节省 ~30% 输出 token
)
```

**预期总节省**: ~50% 输出 token

---

## 自定义测试

### 示例 1: 测试不同的 max_reply_tokens

```python
import asyncio
from app.core.config import PromptConfig
from examples.phase3_token_analysis_example import run_complete_flow_with_config

async def test_different_lengths():
    configs = [
        ("short", 50),
        ("normal", 100),
        ("long", 200),
    ]
    
    for name, max_tokens in configs:
        await run_complete_flow_with_config(
            user_id="test_user",
            conversation=messages,
            prompt_config=PromptConfig(max_reply_tokens=max_tokens),
            trace_file=f"logs/trace_{name}.jsonl"
        )

asyncio.run(test_different_lengths())
```

### 示例 2: 测试推理控制的影响

```python
async def test_reasoning_impact():
    # 包含推理
    await run_complete_flow_with_config(
        user_id="test_user",
        conversation=messages,
        prompt_config=PromptConfig(include_reasoning=True),
        trace_file="logs/trace_with_reasoning.jsonl"
    )
    
    # 不包含推理
    await run_complete_flow_with_config(
        user_id="test_user",
        conversation=messages,
        prompt_config=PromptConfig(include_reasoning=False),
        trace_file="logs/trace_without_reasoning.jsonl"
    )

asyncio.run(test_reasoning_impact())
```

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `phase3_token_analysis_example.py` | 完整的 token 分析示例脚本 |
| `../scripts/analyze_trace.py` | Trace 文件分析工具 |
| `../PHASE3_USAGE_GUIDE.md` | 详细使用指南 |
| `README_PHASE3.md` | 本文件 |

---

## 常见问题

### Q: 如何启用 trace 日志？

A: 在 `.env` 文件中设置：
```bash
TRACE_ENABLED=true
TRACE_LOG_LLM_PROMPT=true
TRACE_FILE_PATH=logs/trace.jsonl
```

### Q: Trace 文件在哪里？

A: 默认在 `logs/` 目录下，文件名为 `trace.jsonl` 或自定义的名称。

### Q: 如何查看完整的 prompt 和 response？

A: 使用 `--detailed` 标志：
```bash
python scripts/analyze_trace.py logs/trace.jsonl --detailed
```

### Q: 为什么 token 减少不明显？

A: 检查以下几点：
1. 确认配置正确应用（`include_reasoning=False`）
2. 确认使用了紧凑模式（`use_compact_schemas=True`）
3. 确认 `max_reply_tokens` 设置合理
4. 查看详细的 trace 对比确认差异

---

## 下一步

1. 运行示例脚本查看效果
2. 阅读 [详细使用指南](../PHASE3_USAGE_GUIDE.md)
3. 根据实际需求调整配置
4. 在生产环境中应用优化

---

**相关文档**:
- [Phase 3 完成报告](../PHASE3_COMPLETION_REPORT.md)
- [Phase 3 快速总结](../PHASE3_SUMMARY.md)
- [详细使用指南](../PHASE3_USAGE_GUIDE.md)
