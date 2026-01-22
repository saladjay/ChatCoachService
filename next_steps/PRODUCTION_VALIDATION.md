# 生产验证计划 (Production Validation Plan)

**目标**: 在真实环境中验证 Phase 3 优化效果  
**预计时间**: 1-2 周  
**优先级**: ⭐⭐⭐ 高

---

## 📋 概述

Phase 3 的实现已完成，但实际的 token 减少量需要在真实 LLM 调用中测量。本文档描述如何进行生产验证。

---

## 🎯 验证目标

### 主要目标
1. **测量实际 token 减少量**
   - 输入 token 减少
   - 输出 token 减少
   - 总体 token 减少

2. **验证回复质量**
   - 回复相关性
   - 用户满意度
   - 亲密度检查通过率

3. **评估性能影响**
   - 响应延迟
   - 错误率
   - 系统稳定性

4. **计算成本节省**
   - 每请求成本
   - 每日成本
   - 月度成本

---

## 📊 验证阶段

### 阶段 1: 本地测试 (1-2 天)

**目标**: 使用真实 LLM 进行本地测试

**步骤**:

1. **配置环境**
   ```bash
   # 在 .env 中启用 trace 日志
   TRACE_ENABLED=true
   TRACE_LOG_LLM_PROMPT=true
   TRACE_FILE_PATH=logs/trace.jsonl
   
   # 配置 Phase 3 优化
   PROMPT_INCLUDE_REASONING=false
   PROMPT_MAX_REPLY_TOKENS=100
   PROMPT_USE_COMPACT_SCHEMAS=true
   ```

2. **运行基准测试**
   ```bash
   # 使用原始配置运行
   python examples/phase3_token_analysis_example.py
   ```

3. **分析结果**
   ```bash
   # 对比 baseline 和 optimized
   python scripts/analyze_trace.py \
     logs/trace_baseline.jsonl \
     logs/trace_optimized.jsonl \
     --compare --detailed
   ```

4. **记录指标**
   - 总 token 数
   - 输入/输出 token 分布
   - 成本对比
   - 响应时间

**成功标准**:
- ✅ Token 减少 ≥ 40%
- ✅ 回复质量保持不变
- ✅ 延迟增加 < 5%
- ✅ 无错误发生

---

### 阶段 2: 金丝雀部署 (2-3 天)

**目标**: 在 5% 真实流量上测试

**步骤**:

1. **部署配置**
   ```python
   # 在 app/core/container.py 中
   # 为 5% 用户启用 Phase 3 优化
   
   def should_use_phase3_optimization(user_id: str) -> bool:
       # 简单的哈希分流
       return hash(user_id) % 100 < 5
   
   # 在创建 reply_generator 时
   if should_use_phase3_optimization(user_id):
       prompt_config = PromptConfig(
           include_reasoning=False,
           max_reply_tokens=100,
           use_compact_schemas=True
       )
   else:
       prompt_config = PromptConfig(
           include_reasoning=True,
           max_reply_tokens=200,
           use_compact_schemas=False
       )
   ```

2. **监控指标**
   - 每小时检查一次
   - 对比实验组和对照组
   - 记录异常情况

3. **收集数据**
   ```bash
   # 每天分析 trace 日志
   python scripts/analyze_trace.py logs/trace_production.jsonl
   ```

**监控指标**:
- Token 使用量 (实验组 vs 对照组)
- 响应时间 (p50, p95, p99)
- 错误率
- 用户满意度评分

**成功标准**:
- ✅ Token 减少 ≥ 40%
- ✅ 错误率 < 1%
- ✅ 用户满意度无下降
- ✅ 无严重问题

---

### 阶段 3: 扩大部署 (3-5 天)

**目标**: 逐步扩大到 25% → 50% → 100%

**步骤**:

1. **25% 流量** (2 天)
   - 修改分流比例到 25%
   - 持续监控 48 小时
   - 收集更多数据

2. **50% 流量** (2 天)
   - 修改分流比例到 50%
   - 对比两组数据
   - 调整参数（如需要）

3. **100% 流量** (1 天)
   - 全量部署
   - 最终验证
   - 记录最终指标

**成功标准**:
- ✅ 所有阶段指标达标
- ✅ 无回滚事件
- ✅ 用户反馈正面

---

## 📈 数据收集

### 需要收集的数据

#### Token 指标
```python
# 每个请求记录
{
    "user_id": "xxx",
    "request_id": "xxx",
    "timestamp": "2026-01-22T10:00:00Z",
    "config": "optimized",  # or "baseline"
    "tokens": {
        "scene_analysis_input": 350,
        "scene_analysis_output": 80,
        "strategy_planning_input": 190,
        "strategy_planning_output": 50,
        "reply_generation_input": 450,
        "reply_generation_output": 120,
        "total_input": 990,
        "total_output": 250,
        "total": 1240
    },
    "cost_usd": 0.0062
}
```

#### 质量指标
```python
{
    "user_id": "xxx",
    "request_id": "xxx",
    "quality_metrics": {
        "relevance_score": 0.85,  # 0-1
        "intimacy_check_passed": true,
        "user_satisfaction": 4.5,  # 1-5
        "response_time_ms": 1250
    }
}
```

#### 性能指标
```python
{
    "timestamp": "2026-01-22T10:00:00Z",
    "period": "1h",
    "metrics": {
        "total_requests": 1000,
        "successful_requests": 995,
        "failed_requests": 5,
        "avg_latency_ms": 1200,
        "p95_latency_ms": 2000,
        "p99_latency_ms": 3000,
        "error_rate": 0.005
    }
}
```

---

## 🔍 分析方法

### Token 减少分析

```python
# 计算 token 减少百分比
def calculate_token_reduction(baseline_tokens, optimized_tokens):
    reduction = (baseline_tokens - optimized_tokens) / baseline_tokens * 100
    return reduction

# 示例
baseline_avg = 2000  # 平均 baseline tokens
optimized_avg = 1200  # 平均 optimized tokens
reduction = calculate_token_reduction(baseline_avg, optimized_avg)
print(f"Token reduction: {reduction:.1f}%")  # 40.0%
```

### 成本节省分析

```python
# 计算成本节省
def calculate_cost_savings(baseline_cost, optimized_cost, daily_requests):
    cost_per_request = baseline_cost - optimized_cost
    daily_savings = cost_per_request * daily_requests
    monthly_savings = daily_savings * 30
    annual_savings = daily_savings * 365
    
    return {
        "per_request": cost_per_request,
        "daily": daily_savings,
        "monthly": monthly_savings,
        "annual": annual_savings
    }

# 示例
baseline_cost = 0.010  # $0.010 per request
optimized_cost = 0.006  # $0.006 per request
daily_requests = 10000

savings = calculate_cost_savings(baseline_cost, optimized_cost, daily_requests)
print(f"Annual savings: ${savings['annual']:,.2f}")  # $14,600.00
```

### 质量对比分析

```python
# 对比质量指标
def compare_quality_metrics(baseline_metrics, optimized_metrics):
    comparison = {}
    
    for metric in baseline_metrics:
        baseline_val = baseline_metrics[metric]
        optimized_val = optimized_metrics[metric]
        
        if isinstance(baseline_val, (int, float)):
            diff = optimized_val - baseline_val
            diff_pct = (diff / baseline_val) * 100 if baseline_val != 0 else 0
            
            comparison[metric] = {
                "baseline": baseline_val,
                "optimized": optimized_val,
                "difference": diff,
                "difference_pct": diff_pct
            }
    
    return comparison
```

---

## 📊 报告模板

### 每日报告

```markdown
# Phase 3 验证 - 每日报告

**日期**: 2026-01-22  
**阶段**: 金丝雀部署 (5% 流量)

## Token 使用

| 指标 | Baseline | Optimized | 减少 |
|------|----------|-----------|------|
| 平均输入 token | 1,800 | 1,200 | -33.3% |
| 平均输出 token | 650 | 325 | -50.0% |
| 平均总 token | 2,450 | 1,525 | -37.8% |

## 成本

| 指标 | Baseline | Optimized | 节省 |
|------|----------|-----------|------|
| 每请求成本 | $0.0123 | $0.0076 | $0.0047 |
| 每日成本 | $123.00 | $76.00 | $47.00 |

## 质量

| 指标 | Baseline | Optimized | 变化 |
|------|----------|-----------|------|
| 相关性评分 | 0.85 | 0.84 | -1.2% |
| 用户满意度 | 4.5 | 4.4 | -2.2% |
| 亲密度通过率 | 95% | 94% | -1.0% |

## 性能

| 指标 | Baseline | Optimized | 变化 |
|------|----------|-----------|------|
| 平均延迟 | 1,200ms | 1,150ms | -4.2% |
| P95 延迟 | 2,000ms | 1,900ms | -5.0% |
| 错误率 | 0.5% | 0.6% | +0.1% |

## 结论

✅ Token 减少达到目标 (37.8%)
✅ 成本节省显著 ($47/天)
⚠️ 质量略有下降但在可接受范围内
✅ 性能略有提升
✅ 错误率保持稳定

**建议**: 继续扩大到 25% 流量
```

---

## ⚠️ 风险与应对

### 风险 1: Token 减少不达预期

**应对措施**:
- 检查配置是否正确应用
- 分析哪个阶段减少不足
- 调整 `max_reply_tokens` 参数
- 考虑更激进的优化

### 风险 2: 质量下降

**应对措施**:
- 立即回滚到 baseline
- 分析质量下降的原因
- 调整 `include_reasoning` 设置
- 增加 `max_reply_tokens` 限制

### 风险 3: 性能问题

**应对措施**:
- 检查是否有新的瓶颈
- 优化代码性能
- 考虑缓存策略
- 调整并发设置

### 风险 4: 错误率上升

**应对措施**:
- 立即回滚
- 检查错误日志
- 修复 bug
- 增加错误处理

---

## ✅ 验证清单

### 部署前
- [ ] 所有单元测试通过
- [ ] 配置文件准备就绪
- [ ] 监控系统配置完成
- [ ] 回滚计划已制定
- [ ] 团队成员已通知

### 金丝雀阶段
- [ ] 5% 流量部署成功
- [ ] 监控数据正常收集
- [ ] 无严重错误
- [ ] Token 减少达到预期
- [ ] 质量指标稳定

### 扩大部署
- [ ] 25% 流量验证通过
- [ ] 50% 流量验证通过
- [ ] 100% 流量部署成功
- [ ] 最终指标记录完成
- [ ] 文档更新完成

---

## 📝 最终报告

验证完成后，创建最终报告：

```markdown
# Phase 3 生产验证 - 最终报告

**验证期间**: 2026-01-22 至 2026-02-05  
**总流量**: 1,000,000 请求

## 主要发现

1. **Token 减少**: 实际减少 42.3% (超过预期 40%)
2. **成本节省**: 每月节省 $14,200
3. **质量影响**: 质量指标下降 < 2% (可接受)
4. **性能影响**: 延迟减少 4.5% (正面影响)

## 建议

- ✅ 全量部署 Phase 3 优化
- ✅ 继续监控质量指标
- ✅ 考虑实施 Phase 4 (内存压缩)
```

---

## 🚀 下一步

验证成功后：
1. 更新 `SYSTEM_STATUS.md`
2. 记录最终指标到 `PHASE3_COMPLETION_REPORT.md`
3. 决定是否继续 Phase 4
4. 分享成功经验

---

**创建日期**: 2026-01-22  
**最后更新**: 2026-01-22  
**版本**: 1.0
