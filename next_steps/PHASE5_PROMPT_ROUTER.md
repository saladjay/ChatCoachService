# Phase 5: 智能路由 (Prompt Router)

**目标**: 根据场景自动选择最优模型，减少 40-60% 成本  
**预计时间**: 1 周  
**优先级**: ⭐⭐ 中

---

## 📋 概述

不同的场景对模型能力的要求不同。Phase 5 通过智能路由，根据对话场景、亲密度、稳定性等因素，自动选择最合适的模型和配置，在保证质量的同时最大化成本效益。

---

## 🎯 目标

### 主要目标
1. **成本优化**
   - 目标: 40-60% 成本减少
   - 保持质量不变
   - 智能模型选择

2. **质量保证**
   - 关键场景使用高质量模型
   - 简单场景使用经济模型
   - 动态调整策略

3. **灵活配置**
   - 可配置的路由规则
   - A/B 测试支持
   - 实时调整能力

---

## 🏗️ 架构设计

### 路由决策流程

```
LLM 调用请求
    ↓
提取路由上下文
    ↓
路由器分析
    ↓
选择模型/配置
    ↓
执行 LLM 调用
    ↓
记录决策和结果
```

### 路由上下文

```python
@dataclass
class RoutingContext:
    """路由决策所需的上下文信息"""
    
    # 场景信息
    scenario: str  # SAFE, BALANCED, RISKY, etc.
    intimacy_level: int  # 0-100
    current_intimacy_level: int  # 0-100
    
    # 稳定性
    relationship_stability: str  # stable, unstable, critical
    
    # 任务类型
    task_type: str  # scene, strategy, generation
    
    # 质量要求
    quality_tier: str  # cheap, normal, premium
    
    # 用户信息
    user_id: str
    is_vip: bool  # VIP 用户可能需要更高质量
```

---

## 🎛️ 路由规则设计

### 路由表

```python
ROUTING_TABLE = {
    # 场景分析 - 使用快速模型
    "scene_analysis": {
        "default": {
            "provider": "dashscope",
            "model": "qwen-turbo",  # 快速且便宜
            "max_tokens": 200,
            "temperature": 0.3
        }
    },
    
    # 策略规划 - 根据场景选择
    "strategy_planning": {
        "SAFE": {
            "provider": "dashscope",
            "model": "qwen-turbo",
            "max_tokens": 150,
            "temperature": 0.5
        },
        "BALANCED": {
            "provider": "dashscope",
            "model": "qwen-plus",
            "max_tokens": 200,
            "temperature": 0.6
        },
        "RISKY": {
            "provider": "dashscope",
            "model": "qwen-max",  # 高风险场景需要更好的模型
            "max_tokens": 250,
            "temperature": 0.7
        },
        "RECOVERY": {
            "provider": "dashscope",
            "model": "qwen-max",  # 修复期需要谨慎
            "max_tokens": 250,
            "temperature": 0.5
        }
    },
    
    # 回复生成 - 根据亲密度和稳定性选择
    "reply_generation": {
        # 低亲密度 + 稳定 = 经济模型
        "low_intimacy_stable": {
            "provider": "dashscope",
            "model": "qwen-turbo",
            "max_tokens": 100,
            "temperature": 0.7
        },
        
        # 中等亲密度 = 标准模型
        "medium_intimacy": {
            "provider": "dashscope",
            "model": "qwen-plus",
            "max_tokens": 150,
            "temperature": 0.7
        },
        
        # 高亲密度 = 高质量模型
        "high_intimacy": {
            "provider": "dashscope",
            "model": "qwen-max",
            "max_tokens": 200,
            "temperature": 0.8
        },
        
        # 不稳定关系 = 高质量模型（需要谨慎）
        "unstable": {
            "provider": "dashscope",
            "model": "qwen-max",
            "max_tokens": 200,
            "temperature": 0.6
        },
        
        # VIP 用户 = 最高质量
        "vip": {
            "provider": "dashscope",
            "model": "qwen-max",
            "max_tokens": 250,
            "temperature": 0.8
        }
    }
}
```

### 路由逻辑

```python
class PromptRouter:
    """智能 Prompt 路由器"""
    
    def __init__(self, routing_table: Dict = None):
        self.routing_table = routing_table or ROUTING_TABLE
        self.decision_log = []  # 记录路由决策
    
    def route(self, context: RoutingContext) -> RoutingDecision:
        """根据上下文做出路由决策
        
        Args:
            context: 路由上下文
        
        Returns:
            路由决策（模型、配置等）
        """
        task_type = context.task_type
        
        # 场景分析 - 总是使用快速模型
        if task_type == "scene_analysis":
            config = self.routing_table["scene_analysis"]["default"]
        
        # 策略规划 - 根据场景选择
        elif task_type == "strategy_planning":
            scenario = context.scenario
            config = self.routing_table["strategy_planning"].get(
                scenario,
                self.routing_table["strategy_planning"]["BALANCED"]
            )
        
        # 回复生成 - 复杂的路由逻辑
        elif task_type == "reply_generation":
            config = self._route_reply_generation(context)
        
        else:
            # 默认配置
            config = {
                "provider": "dashscope",
                "model": "qwen-plus",
                "max_tokens": 200,
                "temperature": 0.7
            }
        
        # 创建路由决策
        decision = RoutingDecision(
            provider=config["provider"],
            model=config["model"],
            max_tokens=config["max_tokens"],
            temperature=config["temperature"],
            reasoning=self._explain_decision(context, config)
        )
        
        # 记录决策
        self._log_decision(context, decision)
        
        return decision
    
    def _route_reply_generation(self, context: RoutingContext) -> Dict:
        """回复生成的路由逻辑"""
        
        # VIP 用户 - 最高质量
        if context.is_vip:
            return self.routing_table["reply_generation"]["vip"]
        
        # 不稳定关系 - 高质量模型
        if context.relationship_stability == "unstable":
            return self.routing_table["reply_generation"]["unstable"]
        
        # 根据亲密度选择
        intimacy = context.intimacy_level
        
        if intimacy >= 70:
            # 高亲密度
            return self.routing_table["reply_generation"]["high_intimacy"]
        elif intimacy >= 40:
            # 中等亲密度
            return self.routing_table["reply_generation"]["medium_intimacy"]
        else:
            # 低亲密度 + 稳定
            if context.relationship_stability == "stable":
                return self.routing_table["reply_generation"]["low_intimacy_stable"]
            else:
                return self.routing_table["reply_generation"]["medium_intimacy"]
    
    def _explain_decision(self, context: RoutingContext, config: Dict) -> str:
        """解释路由决策"""
        return f"Task: {context.task_type}, Scenario: {context.scenario}, " \
               f"Intimacy: {context.intimacy_level}, Model: {config['model']}"
    
    def _log_decision(self, context: RoutingContext, decision: RoutingDecision):
        """记录路由决策"""
        self.decision_log.append({
            "timestamp": datetime.now(),
            "context": context,
            "decision": decision
        })
```

---

## 🔗 集成到 LLM Adapter

### 更新 LLMAdapter

```python
class LLMAdapterImpl(BaseLLMAdapter):
    def __init__(
        self,
        router: PromptRouter = None,  # 新增
        trace_service: TraceService = None
    ):
        self.router = router  # 新增
        self.trace_service = trace_service
    
    async def call(self, llm_call: LLMCall) -> LLMResult:
        """执行 LLM 调用（带路由）"""
        
        # 如果有路由器，使用路由决策
        if self.router and llm_call.routing_context:
            decision = self.router.route(llm_call.routing_context)
            
            # 覆盖原有配置
            llm_call.provider = decision.provider
            llm_call.model = decision.model
            llm_call.max_tokens = decision.max_tokens
            llm_call.temperature = decision.temperature
            
            # 记录路由决策
            if self.trace_service:
                self.trace_service.log_routing_decision(decision)
        
        # 执行原有的调用逻辑
        return await self._execute_call(llm_call)
```

### 更新 LLMCall

```python
@dataclass
class LLMCall:
    """LLM 调用请求"""
    
    task_type: str
    prompt: str
    quality: str = "normal"
    user_id: str = "system"
    
    # 路由相关（新增）
    routing_context: Optional[RoutingContext] = None
    
    # 可被路由器覆盖的字段
    provider: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
```

---

## 📊 预期效果

### 成本减少

| 场景 | 原始模型 | 路由后模型 | 成本减少 |
|------|---------|-----------|---------|
| 场景分析 | qwen-plus | qwen-turbo | -60% |
| 策略规划 (SAFE) | qwen-plus | qwen-turbo | -60% |
| 策略规划 (RISKY) | qwen-plus | qwen-max | +50% |
| 回复生成 (低亲密度) | qwen-plus | qwen-turbo | -60% |
| 回复生成 (高亲密度) | qwen-plus | qwen-max | +50% |

### 整体影响

假设请求分布：
- 场景分析: 100% 使用 turbo (-60%)
- 策略规划: 60% SAFE/BALANCED (turbo), 40% RISKY/RECOVERY (max)
- 回复生成: 50% 低亲密度 (turbo), 30% 中等 (plus), 20% 高亲密度 (max)

**加权平均成本减少**: ~45%

---

## 🧪 测试策略

### 单元测试

```python
# tests/test_prompt_router.py

class TestPromptRouter:
    def test_scene_analysis_routing(self):
        """测试场景分析路由"""
        context = RoutingContext(
            task_type="scene_analysis",
            scenario="BALANCED",
            intimacy_level=50
        )
        
        decision = router.route(context)
        
        assert decision.model == "qwen-turbo"
    
    def test_risky_scenario_routing(self):
        """测试高风险场景路由"""
        context = RoutingContext(
            task_type="strategy_planning",
            scenario="RISKY",
            intimacy_level=60
        )
        
        decision = router.route(context)
        
        assert decision.model == "qwen-max"
    
    def test_vip_user_routing(self):
        """测试 VIP 用户路由"""
        context = RoutingContext(
            task_type="reply_generation",
            scenario="BALANCED",
            intimacy_level=50,
            is_vip=True
        )
        
        decision = router.route(context)
        
        assert decision.model == "qwen-max"
```

### A/B 测试

```python
# 对比路由前后的效果
async def ab_test_routing():
    """A/B 测试路由效果"""
    
    # A 组: 不使用路由
    group_a_cost = 0
    group_a_quality = []
    
    # B 组: 使用路由
    group_b_cost = 0
    group_b_quality = []
    
    for request in test_requests:
        # A 组
        result_a = await llm_adapter_without_router.call(request)
        group_a_cost += result_a.cost
        group_a_quality.append(evaluate_quality(result_a))
        
        # B 组
        result_b = await llm_adapter_with_router.call(request)
        group_b_cost += result_b.cost
        group_b_quality.append(evaluate_quality(result_b))
    
    # 对比结果
    cost_reduction = (group_a_cost - group_b_cost) / group_a_cost
    quality_change = (mean(group_b_quality) - mean(group_a_quality)) / mean(group_a_quality)
    
    print(f"成本减少: {cost_reduction:.1%}")
    print(f"质量变化: {quality_change:.1%}")
```

---

## 📈 监控与优化

### 路由决策监控

```python
# 记录每个路由决策
{
    "timestamp": "2026-01-22T10:00:00Z",
    "task_type": "reply_generation",
    "context": {
        "scenario": "BALANCED",
        "intimacy_level": 65,
        "stability": "stable"
    },
    "decision": {
        "model": "qwen-plus",
        "reasoning": "Medium intimacy, stable relationship"
    },
    "result": {
        "cost": 0.005,
        "quality_score": 0.85,
        "latency_ms": 1200
    }
}
```

### 路由效果分析

```python
def analyze_routing_effectiveness():
    """分析路由效果"""
    
    # 按模型统计
    model_stats = {}
    for decision in router.decision_log:
        model = decision.decision.model
        if model not in model_stats:
            model_stats[model] = {
                "count": 0,
                "total_cost": 0,
                "avg_quality": []
            }
        
        model_stats[model]["count"] += 1
        model_stats[model]["total_cost"] += decision.result.cost
        model_stats[model]["avg_quality"].append(decision.result.quality_score)
    
    # 打印统计
    for model, stats in model_stats.items():
        print(f"\n{model}:")
        print(f"  使用次数: {stats['count']}")
        print(f"  总成本: ${stats['total_cost']:.2f}")
        print(f"  平均质量: {mean(stats['avg_quality']):.2f}")
```

---

## ⚙️ 配置与调优

### 动态调整路由规则

```python
# 根据实际数据调整路由表
def optimize_routing_table(performance_data):
    """根据性能数据优化路由表"""
    
    # 分析哪些场景可以使用更便宜的模型
    for scenario, data in performance_data.items():
        if data["quality_score"] > 0.90 and data["model"] == "qwen-max":
            # 质量过高，可以降级
            print(f"建议 {scenario} 降级到 qwen-plus")
        
        elif data["quality_score"] < 0.80 and data["model"] == "qwen-turbo":
            # 质量不足，需要升级
            print(f"建议 {scenario} 升级到 qwen-plus")
```

### A/B 测试框架

```python
class RoutingABTest:
    """路由 A/B 测试框架"""
    
    def __init__(self, variant_a: Dict, variant_b: Dict):
        self.variant_a = variant_a  # 路由规则 A
        self.variant_b = variant_b  # 路由规则 B
        self.results = {"a": [], "b": []}
    
    async def run_test(self, requests: List[LLMCall]):
        """运行 A/B 测试"""
        for request in requests:
            # 随机分配到 A 或 B 组
            variant = "a" if random.random() < 0.5 else "b"
            
            # 使用对应的路由规则
            routing_table = self.variant_a if variant == "a" else self.variant_b
            router = PromptRouter(routing_table)
            
            # 执行请求
            result = await execute_with_router(request, router)
            
            # 记录结果
            self.results[variant].append(result)
    
    def analyze_results(self):
        """分析 A/B 测试结果"""
        # 对比成本、质量、延迟等指标
        pass
```

---

## 📅 实施计划

### Week 1: 核心实现
- Day 1-2: 创建 `PromptRouter` 类
- Day 3-4: 集成到 `LLMAdapter`
- Day 5: 更新所有服务以提供路由上下文

### Week 2: 测试与优化
- Day 1-2: 单元测试
- Day 3-4: A/B 测试
- Day 5: 路由规则调优

### Week 3: 部署与监控
- Day 1-2: 金丝雀部署
- Day 3-5: 全量部署
- Day 6-7: 监控和优化

---

## 🎯 成功标准

- ✅ 成本减少 ≥ 40%
- ✅ 质量指标无下降
- ✅ 路由决策延迟 < 10ms
- ✅ 所有测试通过
- ✅ 监控系统正常运行

---

## ⚠️ 注意事项

### 质量风险
- **问题**: 过度优化可能降低质量
- **缓解**: 设置质量下限，定期评估
- **监控**: 实时质量监控，自动告警

### 复杂性
- **问题**: 路由逻辑可能变得复杂
- **缓解**: 保持规则简单明了
- **文档**: 详细记录每个路由决策

### 模型可用性
- **问题**: 某些模型可能不可用
- **缓解**: 实现降级策略
- **监控**: 监控模型可用性

---

## 📚 参考资料

- Phase 3 完成报告: `PHASE3_COMPLETION_REPORT.md`
- Phase 4 设计: `PHASE4_MEMORY_COMPRESSION.md`
- 实施清单: `how_to_reduce_token/IMPLEMENTATION_CHECKLIST.md`

---

**创建日期**: 2026-01-22  
**最后更新**: 2026-01-22  
**版本**: 1.0
