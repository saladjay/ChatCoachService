# 增强功能 (Enhancements)

**目标**: 为现有系统添加监控、A/B 测试等功能  
**预计时间**: 2-3 周  
**优先级**: ⭐ 中低

---

## 📋 概述

在完成核心优化后，可以添加一些增强功能来提升系统的可观测性、可测试性和可维护性。

---

## 🎯 增强功能列表

### 1. Token 使用监控仪表板 📊

**目标**: 实时监控 token 使用情况

**功能**:
- 实时 token 使用统计
- 按时间段查看趋势
- 按用户/场景分组
- 成本预测和告警

**实现**:
```python
# app/services/token_monitor.py

class TokenMonitor:
    """Token 使用监控服务"""
    
    def __init__(self, storage: MetricsStorage):
        self.storage = storage
    
    async def record_usage(self, usage: TokenUsage):
        """记录 token 使用"""
        await self.storage.save({
            "timestamp": datetime.now(),
            "user_id": usage.user_id,
            "task_type": usage.task_type,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "cost_usd": usage.cost_usd,
            "model": usage.model,
            "provider": usage.provider
        })
    
    async def get_stats(
        self,
        start_time: datetime,
        end_time: datetime,
        group_by: str = "hour"
    ) -> Dict:
        """获取统计数据"""
        data = await self.storage.query(start_time, end_time)
        
        # 按时间分组
        grouped = self._group_by_time(data, group_by)
        
        return {
            "total_tokens": sum(d["total_tokens"] for d in data),
            "total_cost": sum(d["cost_usd"] for d in data),
            "avg_tokens_per_request": mean([d["total_tokens"] for d in data]),
            "timeline": grouped
        }
```

**仪表板界面**:
```
Token 使用监控仪表板
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 今日统计 (2026-01-22)
┌─────────────────────────────────────────────────────────────┐
│ 总请求数: 10,000                                             │
│ 总 Token: 12,500,000                                         │
│ 总成本: $62.50                                               │
│ 平均 Token/请求: 1,250                                       │
└─────────────────────────────────────────────────────────────┘

📈 Token 使用趋势 (最近 24 小时)
  2000 ┤                                    ╭─╮
  1800 ┤                              ╭─────╯ ╰─╮
  1600 ┤                        ╭─────╯         ╰─╮
  1400 ┤                  ╭─────╯                 ╰─╮
  1200 ┤            ╭─────╯                         ╰─╮
  1000 ┤      ╭─────╯                                 ╰─╮
   800 ┤╭─────╯                                         ╰─╮
       └┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─
        00:00 03:00 06:00 09:00 12:00 15:00 18:00 21:00 24:00

💰 成本分布 (按任务类型)
┌─────────────────────────────────────────────────────────────┐
│ 场景分析:     $12.50 (20%) ████████                         │
│ 策略规划:     $18.75 (30%) ████████████                     │
│ 回复生成:     $31.25 (50%) ████████████████████             │
└─────────────────────────────────────────────────────────────┘

🎯 优化建议
• 场景分析可以使用更便宜的模型 (预计节省 $5/天)
• 低亲密度对话可以减少 max_tokens (预计节省 $8/天)
```

---

### 2. A/B 测试框架 🧪

**目标**: 系统化地测试不同配置

**功能**:
- 配置多个测试变体
- 自动流量分配
- 实时结果对比
- 统计显著性检验

**实现**:
```python
# app/services/ab_testing.py

class ABTestFramework:
    """A/B 测试框架"""
    
    def __init__(self):
        self.experiments = {}
        self.results = {}
    
    def create_experiment(
        self,
        name: str,
        variants: Dict[str, PromptConfig],
        traffic_split: Dict[str, float]
    ):
        """创建实验
        
        Args:
            name: 实验名称
            variants: 变体配置 {"A": config_a, "B": config_b}
            traffic_split: 流量分配 {"A": 0.5, "B": 0.5}
        """
        self.experiments[name] = {
            "variants": variants,
            "traffic_split": traffic_split,
            "start_time": datetime.now(),
            "status": "running"
        }
    
    def assign_variant(self, experiment_name: str, user_id: str) -> str:
        """为用户分配变体"""
        experiment = self.experiments[experiment_name]
        
        # 基于用户 ID 的一致性哈希
        hash_value = hash(f"{experiment_name}:{user_id}") % 100
        
        cumulative = 0
        for variant, split in experiment["traffic_split"].items():
            cumulative += split * 100
            if hash_value < cumulative:
                return variant
        
        return list(experiment["variants"].keys())[0]
    
    def record_result(
        self,
        experiment_name: str,
        variant: str,
        metrics: Dict
    ):
        """记录实验结果"""
        if experiment_name not in self.results:
            self.results[experiment_name] = {}
        
        if variant not in self.results[experiment_name]:
            self.results[experiment_name][variant] = []
        
        self.results[experiment_name][variant].append(metrics)
    
    def analyze_experiment(self, experiment_name: str) -> Dict:
        """分析实验结果"""
        results = self.results[experiment_name]
        
        analysis = {}
        for variant, data in results.items():
            analysis[variant] = {
                "sample_size": len(data),
                "avg_tokens": mean([d["total_tokens"] for d in data]),
                "avg_cost": mean([d["cost_usd"] for d in data]),
                "avg_quality": mean([d["quality_score"] for d in data]),
                "avg_latency": mean([d["latency_ms"] for d in data])
            }
        
        # 计算统计显著性
        if len(results) == 2:
            variants = list(results.keys())
            significance = self._calculate_significance(
                results[variants[0]],
                results[variants[1]]
            )
            analysis["significance"] = significance
        
        return analysis
```

**使用示例**:
```python
# 创建实验
ab_test = ABTestFramework()
ab_test.create_experiment(
    name="reasoning_control_test",
    variants={
        "A": PromptConfig(include_reasoning=True, max_reply_tokens=200),
        "B": PromptConfig(include_reasoning=False, max_reply_tokens=100)
    },
    traffic_split={"A": 0.5, "B": 0.5}
)

# 在请求处理中
variant = ab_test.assign_variant("reasoning_control_test", user_id)
config = ab_test.experiments["reasoning_control_test"]["variants"][variant]

# 使用配置生成回复
result = await generate_reply(config=config)

# 记录结果
ab_test.record_result(
    "reasoning_control_test",
    variant,
    {
        "total_tokens": result.total_tokens,
        "cost_usd": result.cost,
        "quality_score": evaluate_quality(result),
        "latency_ms": result.latency
    }
)

# 分析结果
analysis = ab_test.analyze_experiment("reasoning_control_test")
print(analysis)
```

---

### 3. 动态优化 🔄

**目标**: 根据实时数据自动调整配置

**功能**:
- 自动检测性能问题
- 动态调整 token 限制
- 自适应模型选择
- 自动回滚机制

**实现**:
```python
# app/services/dynamic_optimizer.py

class DynamicOptimizer:
    """动态优化器"""
    
    def __init__(self, monitor: TokenMonitor):
        self.monitor = monitor
        self.current_config = PromptConfig.from_env()
        self.optimization_history = []
    
    async def optimize(self):
        """执行优化"""
        # 获取最近的性能数据
        stats = await self.monitor.get_stats(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now()
        )
        
        # 分析是否需要优化
        if self._should_optimize(stats):
            new_config = self._calculate_optimal_config(stats)
            
            # 应用新配置
            await self._apply_config(new_config)
            
            # 记录优化
            self.optimization_history.append({
                "timestamp": datetime.now(),
                "old_config": self.current_config,
                "new_config": new_config,
                "reason": self._explain_optimization(stats)
            })
            
            self.current_config = new_config
    
    def _should_optimize(self, stats: Dict) -> bool:
        """判断是否需要优化"""
        # 成本过高
        if stats["total_cost"] > COST_THRESHOLD:
            return True
        
        # Token 使用过多
        if stats["avg_tokens_per_request"] > TOKEN_THRESHOLD:
            return True
        
        # 质量下降
        if stats.get("avg_quality", 1.0) < QUALITY_THRESHOLD:
            return True
        
        return False
    
    def _calculate_optimal_config(self, stats: Dict) -> PromptConfig:
        """计算最优配置"""
        config = self.current_config.copy()
        
        # 如果成本过高，减少 token 限制
        if stats["total_cost"] > COST_THRESHOLD:
            config.max_reply_tokens = max(
                50,
                config.max_reply_tokens - 20
            )
        
        # 如果质量下降，增加 token 限制
        if stats.get("avg_quality", 1.0) < QUALITY_THRESHOLD:
            config.max_reply_tokens = min(
                200,
                config.max_reply_tokens + 20
            )
        
        return config
```

---

### 4. 质量监控 ✅

**目标**: 持续监控回复质量

**功能**:
- 自动质量评估
- 质量趋势分析
- 异常检测和告警
- 质量报告生成

**实现**:
```python
# app/services/quality_monitor.py

class QualityMonitor:
    """质量监控服务"""
    
    def __init__(self, evaluator: QualityEvaluator):
        self.evaluator = evaluator
        self.quality_history = []
    
    async def evaluate_reply(
        self,
        request: ReplyGenerationInput,
        reply: LLMResult
    ) -> QualityScore:
        """评估回复质量"""
        score = await self.evaluator.evaluate(request, reply)
        
        # 记录质量分数
        self.quality_history.append({
            "timestamp": datetime.now(),
            "user_id": request.user_id,
            "scenario": request.scene.scenario,
            "intimacy_level": request.scene.intimacy_level,
            "score": score
        })
        
        # 检查是否需要告警
        if score.overall < QUALITY_THRESHOLD:
            await self._send_alert(request, reply, score)
        
        return score
    
    async def get_quality_report(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict:
        """生成质量报告"""
        data = [
            d for d in self.quality_history
            if start_time <= d["timestamp"] <= end_time
        ]
        
        return {
            "period": f"{start_time} to {end_time}",
            "total_evaluations": len(data),
            "avg_quality": mean([d["score"].overall for d in data]),
            "quality_by_scenario": self._group_by_scenario(data),
            "quality_trend": self._calculate_trend(data),
            "alerts": self._get_alerts(start_time, end_time)
        }
```

---

### 5. 成本预测 💰

**目标**: 预测未来的 token 使用和成本

**功能**:
- 基于历史数据预测
- 不同场景的成本模拟
- 预算告警
- 成本优化建议

**实现**:
```python
# app/services/cost_predictor.py

class CostPredictor:
    """成本预测服务"""
    
    def __init__(self, monitor: TokenMonitor):
        self.monitor = monitor
    
    async def predict_daily_cost(self) -> Dict:
        """预测每日成本"""
        # 获取最近 7 天的数据
        history = await self.monitor.get_stats(
            start_time=datetime.now() - timedelta(days=7),
            end_time=datetime.now(),
            group_by="day"
        )
        
        # 计算趋势
        daily_costs = [d["total_cost"] for d in history["timeline"]]
        trend = self._calculate_trend(daily_costs)
        
        # 预测明天的成本
        predicted_cost = daily_costs[-1] * (1 + trend)
        
        return {
            "predicted_daily_cost": predicted_cost,
            "trend": trend,
            "confidence": 0.85,
            "historical_avg": mean(daily_costs)
        }
    
    async def simulate_optimization(
        self,
        config: PromptConfig
    ) -> Dict:
        """模拟优化效果"""
        # 获取当前成本
        current_stats = await self.monitor.get_stats(
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now()
        )
        
        # 估算优化后的成本
        # (基于 Phase 3 的预期减少比例)
        estimated_reduction = 0.40  # 40% 减少
        
        if not config.include_reasoning:
            estimated_reduction += 0.10  # 额外 10%
        
        if config.max_reply_tokens < 100:
            estimated_reduction += 0.05  # 额外 5%
        
        optimized_cost = current_stats["total_cost"] * (1 - estimated_reduction)
        
        return {
            "current_daily_cost": current_stats["total_cost"],
            "optimized_daily_cost": optimized_cost,
            "estimated_savings": current_stats["total_cost"] - optimized_cost,
            "reduction_percentage": estimated_reduction * 100
        }
```

---

### 6. 配置管理界面 ⚙️

**目标**: 可视化配置管理

**功能**:
- Web 界面配置编辑
- 配置版本管理
- 配置回滚
- 配置对比

**实现**:
```python
# app/api/config_management.py

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/config")

@router.get("/current")
async def get_current_config():
    """获取当前配置"""
    return {
        "prompt": settings.prompt.dict(),
        "llm": settings.llm.dict(),
        "orchestrator": settings.orchestrator.dict()
    }

@router.post("/update")
async def update_config(config: PromptConfig):
    """更新配置"""
    # 验证配置
    if not validate_config(config):
        raise HTTPException(400, "Invalid configuration")
    
    # 保存旧配置
    old_config = settings.prompt
    
    # 应用新配置
    settings.prompt = config
    
    # 记录变更
    await config_history.save({
        "timestamp": datetime.now(),
        "old_config": old_config,
        "new_config": config,
        "user": "admin"
    })
    
    return {"status": "success", "config": config.dict()}

@router.post("/rollback/{version}")
async def rollback_config(version: int):
    """回滚配置"""
    # 获取历史配置
    history = await config_history.get(version)
    
    if not history:
        raise HTTPException(404, "Version not found")
    
    # 回滚
    settings.prompt = history["old_config"]
    
    return {"status": "success", "config": history["old_config"].dict()}
```

---

## 📅 实施优先级

### 高优先级 (立即实施)
1. **Token 使用监控** - 了解当前状态
2. **质量监控** - 确保优化不影响质量

### 中优先级 (1-2 周内)
3. **A/B 测试框架** - 系统化测试
4. **成本预测** - 预算管理

### 低优先级 (有时间再做)
5. **动态优化** - 自动化优化
6. **配置管理界面** - 提升易用性

---

## 🎯 成功标准

- ✅ 监控系统正常运行
- ✅ 能够实时查看 token 使用
- ✅ A/B 测试框架可用
- ✅ 质量监控无告警
- ✅ 成本在预算内

---

## 📚 参考资料

- Phase 3 完成报告: `PHASE3_COMPLETION_REPORT.md`
- 生产验证计划: `PRODUCTION_VALIDATION.md`
- Token 优化分析: `TOKEN_OPTIMIZATION_ANALYSIS.md`

---

**创建日期**: 2026-01-22  
**最后更新**: 2026-01-22  
**版本**: 1.0
