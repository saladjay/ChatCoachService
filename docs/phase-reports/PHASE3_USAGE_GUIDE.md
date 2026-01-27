# Phase 3 Usage Guide: Token Analysis and Comparison

本指南介绍如何使用 Phase 3 的工具来分析和对比不同配置下的 token 使用情况。

---

## 目录

1. [快速开始](#快速开始)
2. [运行完整流程示例](#运行完整流程示例)
3. [分析 Trace 文件](#分析-trace-文件)
4. [配置选项](#配置选项)
5. [实际案例](#实际案例)

---

## 快速开始

### 1. 启用 Trace 日志

在 `.env` 文件中启用 trace 日志：

```bash
# Trace Configuration
TRACE_ENABLED=true
TRACE_LEVEL=info
TRACE_FILE_PATH=logs/trace.jsonl
TRACE_LOG_LLM_PROMPT=true
```

### 2. 运行示例脚本

```bash
# 运行 Phase 3 token 分析示例
python examples/phase3_token_analysis_example.py
```

这个脚本会：
- 使用两种配置运行完整流程（baseline 和 optimized）
- 生成两个 trace 文件
- 自动分析和对比 token 使用情况
- 显示详细的输入输出内容

---

## 运行完整流程示例

### 示例 1: 基础配置 vs 优化配置

```python
import asyncio
from app.core.config import PromptConfig
from examples.phase3_token_analysis_example import run_complete_flow_with_config

# 基础配置（包含推理，较长回复）
baseline_config = PromptConfig(
    include_reasoning=True,
    max_reply_tokens=200,
    use_compact_schemas=False
)

# 优化配置（Phase 3 优化）
optimized_config = PromptConfig(
    include_reasoning=False,
    max_reply_tokens=100,
    use_compact_schemas=True
)

# 运行并对比
asyncio.run(run_complete_flow_with_config(
    user_id="test_user",
    conversation=messages,
    prompt_config=baseline_config,
    trace_file="logs/trace_baseline.jsonl"
))

asyncio.run(run_complete_flow_with_config(
    user_id="test_user",
    conversation=messages,
    prompt_config=optimized_config,
    trace_file="logs/trace_optimized.jsonl"
))
```

### 示例 2: 自定义配置测试

```python
# 测试不同的 max_reply_tokens 设置
configs = [
    ("cheap", PromptConfig(max_reply_tokens=50)),
    ("normal", PromptConfig(max_reply_tokens=100)),
    ("premium", PromptConfig(max_reply_tokens=200)),
]

for name, config in configs:
    await run_complete_flow_with_config(
        user_id="test_user",
        conversation=messages,
        prompt_config=config,
        trace_file=f"logs/trace_{name}.jsonl"
    )
```

---

## 分析 Trace 文件

### 工具 1: analyze_trace.py

这是一个命令行工具，用于分析 trace.jsonl 文件。

#### 基本用法

```bash
# 分析单个 trace 文件
python scripts/analyze_trace.py logs/trace.jsonl

# 显示详细信息（包含完整的 prompt 和 response）
python scripts/analyze_trace.py logs/trace.jsonl --detailed

# 对比两个 trace 文件
python scripts/analyze_trace.py logs/trace_baseline.jsonl logs/trace_optimized.jsonl --compare

# 对比并显示详细信息
python scripts/analyze_trace.py logs/trace_baseline.jsonl logs/trace_optimized.jsonl --compare --detailed
```

#### 输出示例

```
================================================================================
COMPARISON REPORT
================================================================================

📊 OVERALL COMPARISON
--------------------------------------------------------------------------------
Metric                    Baseline        Optimized       Change         
--------------------------------------------------------------------------------
Total Tokens              2,450           1,225           +50.0%
Input Tokens              1,800           1,200           +33.3%
Output Tokens             650             325             +50.0%
Total Cost (USD)          $0.012300       $0.006150       +50.0%
Number of Calls           3               3               

📋 PER-CALL COMPARISON
--------------------------------------------------------------------------------

Call #1: scene
  Model: qwen-flash
  Input:  800 → 600 (+25.0%)
  Output: 150 → 75 (+50.0%)
  Total:  950 → 675 (+28.9%)

Call #2: generation
  Model: qwen-flash
  Input:  900 → 500 (+44.4%)
  Output: 450 → 225 (+50.0%)
  Total:  1350 → 725 (+46.3%)
```

### 工具 2: 编程方式分析

```python
from scripts.analyze_trace import load_trace_file, extract_llm_calls

# 加载 trace 文件
entries = load_trace_file("logs/trace.jsonl")
llm_calls = extract_llm_calls(entries)

# 计算总 token 数
total_tokens = sum(call["total_tokens"] for call in llm_calls)
total_cost = sum(call["cost_usd"] for call in llm_calls)

print(f"Total tokens: {total_tokens}")
print(f"Total cost: ${total_cost:.6f}")

# 查看每个调用的详细信息
for i, call in enumerate(llm_calls, 1):
    print(f"\nCall #{i}: {call['task_type']}")
    print(f"  Input tokens: {call['input_tokens']}")
    print(f"  Output tokens: {call['output_tokens']}")
    print(f"  Prompt preview: {call['prompt'][:100]}...")
```

---

## 配置选项

### PromptConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `include_reasoning` | bool | False | 是否在输出中包含推理字段 |
| `max_reply_tokens` | int | 100 | 回复的最大 token 数（20-500） |
| `use_compact_schemas` | bool | True | 是否使用紧凑的输出模式 |

### 环境变量配置

```bash
# 推理控制
PROMPT_INCLUDE_REASONING=false

# 长度约束
PROMPT_MAX_REPLY_TOKENS=100

# 模式压缩
PROMPT_USE_COMPACT_SCHEMAS=true
```

### 预设配置

#### 1. 最大优化（生产环境推荐）

```python
PromptConfig(
    include_reasoning=False,
    max_reply_tokens=100,
    use_compact_schemas=True
)
```

**预期效果**:
- 输出 token 减少: ~50%
- 成本节省: ~50%
- 质量: 保持不变

#### 2. 平衡配置

```python
PromptConfig(
    include_reasoning=False,
    max_reply_tokens=150,
    use_compact_schemas=True
)
```

**预期效果**:
- 输出 token 减少: ~40%
- 成本节省: ~40%
- 质量: 略有提升（更详细的回复）

#### 3. 调试配置

```python
PromptConfig(
    include_reasoning=True,
    max_reply_tokens=200,
    use_compact_schemas=False
)
```

**预期效果**:
- 完整的推理信息
- 更长的回复
- 便于调试和分析

#### 4. 成本敏感配置

```python
PromptConfig(
    include_reasoning=False,
    max_reply_tokens=50,
    use_compact_schemas=True
)
```

**预期效果**:
- 输出 token 减少: ~60%
- 成本节省: ~60%
- 质量: 简洁但完整

---

## 实际案例

### 案例 1: 对比不同配置的效果

```python
"""
测试场景：用户咨询约会建议
目标：对比 baseline 和 optimized 配置的 token 使用情况
"""

import asyncio
from datetime import datetime
from app.models.schemas import Message
from app.core.config import PromptConfig
from examples.phase3_token_analysis_example import run_complete_flow_with_config

async def test_dating_advice():
    conversation = [
        Message(
            id="1",
            speaker="user",
            content="I have a first date tomorrow and I'm nervous.",
            timestamp=datetime.now()
        ),
        Message(
            id="2",
            speaker="assistant",
            content="That's normal! What are you most worried about?",
            timestamp=datetime.now()
        ),
        Message(
            id="3",
            speaker="user",
            content="I'm worried I'll run out of things to talk about.",
            timestamp=datetime.now()
        )
    ]
    
    # Baseline
    baseline_result = await run_complete_flow_with_config(
        user_id="test_user",
        conversation=conversation,
        prompt_config=PromptConfig(
            include_reasoning=True,
            max_reply_tokens=200,
            use_compact_schemas=False
        ),
        trace_file="logs/trace_dating_baseline.jsonl"
    )
    
    # Optimized
    optimized_result = await run_complete_flow_with_config(
        user_id="test_user",
        conversation=conversation,
        prompt_config=PromptConfig(
            include_reasoning=False,
            max_reply_tokens=100,
            use_compact_schemas=True
        ),
        trace_file="logs/trace_dating_optimized.jsonl"
    )
    
    print("✅ Test complete! Analyze with:")
    print("python scripts/analyze_trace.py logs/trace_dating_baseline.jsonl logs/trace_dating_optimized.jsonl --compare --detailed")

asyncio.run(test_dating_advice())
```

### 案例 2: 批量测试不同配置

```python
"""
批量测试不同的 max_reply_tokens 设置
"""

import asyncio
from examples.phase3_token_analysis_example import run_complete_flow_with_config

async def batch_test():
    test_configs = [
        ("ultra_short", 50),
        ("short", 75),
        ("normal", 100),
        ("long", 150),
        ("ultra_long", 200),
    ]
    
    for name, max_tokens in test_configs:
        print(f"\n{'='*80}")
        print(f"Testing: {name} (max_tokens={max_tokens})")
        print(f"{'='*80}")
        
        await run_complete_flow_with_config(
            user_id="test_user",
            conversation=messages,
            prompt_config=PromptConfig(
                include_reasoning=False,
                max_reply_tokens=max_tokens,
                use_compact_schemas=True
            ),
            trace_file=f"logs/trace_{name}.jsonl"
        )
    
    print("\n✅ All tests complete!")
    print("\nAnalyze results:")
    for name, _ in test_configs:
        print(f"  python scripts/analyze_trace.py logs/trace_{name}.jsonl")

asyncio.run(batch_test())
```

### 案例 3: A/B 测试框架

```python
"""
A/B 测试框架：对比不同优化策略
"""

import asyncio
from typing import List, Dict
from app.core.config import PromptConfig

class ABTestFramework:
    def __init__(self):
        self.results = []
    
    async def run_test(
        self,
        test_name: str,
        config: PromptConfig,
        conversations: List[List[Message]]
    ):
        """运行单个测试配置"""
        total_tokens = 0
        total_cost = 0
        
        for i, conv in enumerate(conversations):
            trace_file = f"logs/ab_test_{test_name}_{i}.jsonl"
            
            result = await run_complete_flow_with_config(
                user_id=f"test_user_{i}",
                conversation=conv,
                prompt_config=config,
                trace_file=trace_file
            )
            
            # 分析结果
            analysis = analyze_trace_file(trace_file)
            total_tokens += analysis["total_tokens"]
            total_cost += sum(call["cost_usd"] for call in analysis["llm_calls"])
        
        self.results.append({
            "name": test_name,
            "config": config,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "avg_tokens_per_conv": total_tokens / len(conversations)
        })
    
    def print_results(self):
        """打印 A/B 测试结果"""
        print("\n" + "="*80)
        print("A/B TEST RESULTS")
        print("="*80)
        
        for result in sorted(self.results, key=lambda x: x["total_tokens"]):
            print(f"\n{result['name']}:")
            print(f"  Total tokens: {result['total_tokens']:,}")
            print(f"  Avg per conversation: {result['avg_tokens_per_conv']:.0f}")
            print(f"  Total cost: ${result['total_cost']:.6f}")
            print(f"  Config: reasoning={result['config'].include_reasoning}, "
                  f"max_tokens={result['config'].max_reply_tokens}")

# 使用示例
async def run_ab_test():
    framework = ABTestFramework()
    
    # 准备测试对话
    conversations = [...]  # 多个测试对话
    
    # 测试不同配置
    await framework.run_test("baseline", PromptConfig(
        include_reasoning=True,
        max_reply_tokens=200,
        use_compact_schemas=False
    ), conversations)
    
    await framework.run_test("optimized", PromptConfig(
        include_reasoning=False,
        max_reply_tokens=100,
        use_compact_schemas=True
    ), conversations)
    
    await framework.run_test("ultra_optimized", PromptConfig(
        include_reasoning=False,
        max_reply_tokens=50,
        use_compact_schemas=True
    ), conversations)
    
    framework.print_results()

asyncio.run(run_ab_test())
```

---

## 最佳实践

### 1. 开发阶段

- 使用 `include_reasoning=True` 便于调试
- 使用 `--detailed` 标志查看完整的 prompt 和 response
- 保存 trace 文件用于后续分析

### 2. 测试阶段

- 对比多种配置找到最佳平衡点
- 使用真实对话数据进行测试
- 测量质量指标（不仅仅是 token 数）

### 3. 生产环境

- 使用优化配置（`include_reasoning=False`）
- 根据质量层级设置合适的 `max_reply_tokens`
- 定期分析 trace 文件监控性能

### 4. 监控和优化

- 定期对比不同时期的 trace 文件
- 跟踪 token 使用趋势
- 根据实际效果调整配置

---

## 故障排查

### 问题 1: Trace 文件为空

**原因**: Trace 日志未启用

**解决方案**:
```bash
# 在 .env 中设置
TRACE_ENABLED=true
TRACE_LOG_LLM_PROMPT=true
```

### 问题 2: 无法对比两个文件

**原因**: LLM 调用次数不同

**解决方案**: 确保两个配置使用相同的输入数据和流程

### 问题 3: Token 减少不明显

**原因**: 可能使用了错误的配置

**解决方案**: 检查配置是否正确应用
```python
# 验证配置
print(f"include_reasoning: {config.include_reasoning}")
print(f"max_reply_tokens: {config.max_reply_tokens}")
print(f"use_compact_schemas: {config.use_compact_schemas}")
```

---

## 相关文档

- [Phase 3 完成报告](PHASE3_COMPLETION_REPORT.md)
- [Phase 3 快速总结](PHASE3_SUMMARY.md)
- [Token 优化实施总结](TOKEN_OPTIMIZATION_IMPLEMENTATION.md)
- [实施清单](how_to_reduce_token/IMPLEMENTATION_CHECKLIST.md)

---

**最后更新**: 2026-01-22  
**版本**: 1.0
