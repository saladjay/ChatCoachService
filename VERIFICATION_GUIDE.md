# Token 优化验证指南

## 快速验证

### 方法 1：运行测试脚本

```bash
# 激活虚拟环境
.venv/Scripts/activate.ps1

# 运行测试
python test_token_optimization.py
```

### 方法 2：查看 trace 日志

```bash
# 运行示例
python examples/complete_flow_example.py

# 查看 token 使用情况
# 检查 logs/trace.jsonl 中的 input_tokens 和 output_tokens
```

### 方法 3：对比测试

#### 步骤 1：测试精简版（默认）

```bash
python examples/complete_flow_example.py > output_compact.txt 2>&1
```

记录 `logs/trace.jsonl` 中的 token 数据。

#### 步骤 2：测试完整版

编辑 `app/core/container.py`，找到以下位置并修改：

```python
# 在 create_orchestrator() 方法中

# 修改 Scene Analyzer
scene_analyzer = SceneAnalyzer(
    llm_adapter=llm_adapter,
    use_compact_prompt=False  # 改为 False
)

# 修改 Context Builder
context_builder = ContextBuilder(
    llm_adapter=llm_adapter,
    use_compact_prompt=False  # 改为 False
)

# 修改 Prompt Assembler
prompt_assembler = PromptAssembler(
    user_profile_service=user_profile_service,
    use_compact_prompt=False  # 改为 False
)
```

然后运行：

```bash
python examples/complete_flow_example.py > output_full.txt 2>&1
```

#### 步骤 3：对比结果

```bash
# 对比 token 使用
# 查看两次运行的 logs/trace.jsonl

# 或使用 Python 脚本分析
python analyze_token_usage.py
```

---

## 详细验证

### 1. Token 计数验证

创建分析脚本 `analyze_token_usage.py`：

```python
import json

def analyze_trace_log(filepath):
    """Analyze token usage from trace log."""
    total_input = 0
    total_output = 0
    calls = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            if data.get('type') == 'llm_call_end':
                input_tokens = data.get('input_tokens', 0)
                output_tokens = data.get('output_tokens', 0)
                total_input += input_tokens
                total_output += output_tokens
                
                calls.append({
                    'task_type': data.get('task_type'),
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total': input_tokens + output_tokens,
                    'cost': data.get('cost_usd', 0)
                })
    
    print(f"Total Input Tokens: {total_input}")
    print(f"Total Output Tokens: {total_output}")
    print(f"Total Tokens: {total_input + total_output}")
    print(f"\nBreakdown by task:")
    for call in calls:
        print(f"  {call['task_type']}: {call['input_tokens']} in + {call['output_tokens']} out = {call['total']} total")
    
    return total_input, total_output

if __name__ == "__main__":
    print("Analyzing token usage...")
    analyze_trace_log('logs/trace.jsonl')
```

### 2. Prompt 长度验证

检查生成的 prompt 文件：

```bash
# Prompt 文件保存在 logs/llm_prompts/ 目录
ls -lh logs/llm_prompts/

# 查看最新的 prompt 文件
Get-ChildItem logs/llm_prompts/ | Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

### 3. 质量验证

对比生成的回复质量：

```python
# 运行多次测试，收集回复
# 人工评估或使用自动化评分

responses_compact = []
responses_full = []

# 对比指标：
# - 回复相关性
# - 语言流畅度
# - 策略准确性
# - 用户满意度
```

---

## 预期结果

### Token 减少目标

| 步骤 | 原始 Tokens | 目标 Tokens | 减少比例 |
|------|-------------|-------------|----------|
| Context Builder | 489 | ~350 | -28% |
| Scene Analysis | 496 | ~350 | -29% |
| Reply Generation | 832 | ~450 | -46% |
| **总计** | **2,622** | **~1,500** | **-43%** |

### 验证标准

✅ **成功标准：**
- Token 减少 ≥ 40%
- 生成质量无明显下降
- 响应时间改善
- 无错误或异常

⚠️ **需要调整：**
- Token 减少 < 40%
- 生成质量明显下降
- 出现频繁错误

❌ **需要回滚：**
- 系统不稳定
- 用户体验严重下降
- 无法正常生成回复

---

## 常见问题

### Q1: 如何查看实时 token 使用？

A: 查看日志输出或 `logs/trace.jsonl` 文件：

```bash
# 实时查看日志
tail -f logs/trace.jsonl | grep "input_tokens"
```

### Q2: 精简版和完整版的质量差异大吗？

A: 理论上应该很小。精简版主要是：
- 移除冗余信息
- 使用摘要替代完整文本
- 保留所有关键信息

建议通过 A/B 测试验证实际效果。

### Q3: 如何切换回完整版？

A: 两种方法：

**方法 1：修改代码**
```python
# 在 container.py 中设置
use_compact_prompt=False
```

**方法 2：恢复原始文件**
```bash
cp app/services/prompt_en_original.py app/services/prompt_en.py
```

### Q4: 优化后成本节省多少？

A: 取决于使用的模型和调用频率：

**示例计算（GPT-4）：**
- 原始：2,622 tokens × $0.03/1K = $0.079
- 优化：1,500 tokens × $0.03/1K = $0.045
- 节省：$0.034 per call

**年度节省（1000 calls/day）：**
- $0.034 × 1000 × 365 = $12,410

### Q5: 如何监控长期效果？

A: 建议实施以下监控：

1. **Token 使用趋势**
   - 每日/每周 token 统计
   - 按任务类型分组
   - 成本趋势分析

2. **质量指标**
   - 生成成功率
   - 用户满意度评分
   - 人工审核抽样

3. **性能指标**
   - API 响应时间
   - 错误率
   - 系统稳定性

---

## 故障排除

### 问题 1：Import 错误

```
ImportError: cannot import name 'SCENARIO_PROMPT_COMPACT'
```

**解决方案：**
```bash
# 确保文件存在
ls app/services/prompt_compact.py

# 检查 Python 路径
python -c "import sys; print(sys.path)"
```

### 问题 2：Token 减少不明显

**可能原因：**
- 仍在使用完整版 prompt
- 配置未生效
- 缓存问题

**解决方案：**
```python
# 检查配置
print(scene_analyzer.use_compact_prompt)  # 应该是 True
print(context_builder.use_compact_prompt)  # 应该是 True
```

### 问题 3：生成质量下降

**解决方案：**
1. 检查是否过度精简
2. 调整 `max_messages` 参数
3. 增加关键信息
4. 考虑使用完整版

---

## 下一步行动

### 立即行动
- [ ] 运行 `test_token_optimization.py`
- [ ] 检查 `logs/trace.jsonl` 中的 token 数据
- [ ] 验证生成的回复质量

### 本周完成
- [ ] 进行 A/B 测试（精简版 vs 完整版）
- [ ] 收集至少 100 次调用的数据
- [ ] 分析 token 减少比例和质量影响
- [ ] 根据结果调整优化策略

### 持续监控
- [ ] 设置 token 使用监控仪表板
- [ ] 定期审查优化效果
- [ ] 收集用户反馈
- [ ] 持续迭代优化

---

## 联系支持

如有问题或需要帮助：
1. 查看 `TOKEN_OPTIMIZATION_ANALYSIS.md` 了解详细分析
2. 查看 `TOKEN_OPTIMIZATION_IMPLEMENTATION.md` 了解实施细节
3. 检查 `logs/trace.jsonl` 获取实际数据
4. 参考 `app/services/prompt_en_original.py` 对比原始版本
