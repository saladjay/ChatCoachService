# 监控系统设置 (Monitoring Setup)

**目标**: 建立完整的监控体系  
**预计时间**: 3-5 天  
**优先级**: ⭐⭐⭐ 高

---

## 📋 概述

监控系统是生产环境的必备组件。本文档描述如何为 Token 优化系统建立完整的监控体系。

---

## 🎯 监控目标

### 核心指标
1. **Token 使用量** - 实时追踪 token 消耗
2. **成本** - 监控 API 调用成本
3. **质量** - 追踪回复质量指标
4. **性能** - 监控响应时间和错误率

---

## 📊 监控架构

```
应用层
  ↓ (记录指标)
Trace 日志 (trace.jsonl)
  ↓ (解析)
指标收集器
  ↓ (存储)
时序数据库 (InfluxDB/Prometheus)
  ↓ (可视化)
监控仪表板 (Grafana)
  ↓ (告警)
告警系统 (Email/Slack)
```

---

## 🔧 实施步骤

### 步骤 1: 增强 Trace 日志

**目标**: 确保所有关键指标都被记录

```python
# app/services/trace_service.py

class TraceService:
    """增强的 Trace 服务"""
    
    def log_llm_call(
        self,
        task_type: str,
        prompt: str,
        response: str,
        tokens: Dict[str, int],
        cost: float,
        latency: float,
        metadata: Dict = None
    ):
        """记录 LLM 调用"""
        entry = {
            "type": "llm_call",
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            
            # Token 信息
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "total_tokens": tokens["total"],
            
            # 成本和性能
            "cost_usd": cost,
            "latency_ms": latency,
            
            # 模型信息
            "provider": metadata.get("provider"),
            "model": metadata.get("model"),
            
            # 配置信息
            "config": {
                "include_reasoning": metadata.get("include_reasoning"),
                "max_reply_tokens": metadata.get("max_reply_tokens"),
                "use_compact_schemas": metadata.get("use_compact_schemas")
            },
            
            # 内容（可选）
            "prompt": prompt if self.log_content else None,
            "response": response if self.log_content else None
        }
        
        self._write_to_file(entry)
        self._send_to_metrics_collector(entry)  # 新增
```

---

### 步骤 2: 设置指标收集器

**选项 A: 使用 Prometheus**

```python
# app/services/metrics_collector.py

from prometheus_client import Counter, Histogram, Gauge

# 定义指标
token_usage = Counter(
    'llm_tokens_total',
    'Total tokens used',
    ['task_type', 'token_type']  # input/output
)

llm_cost = Counter(
    'llm_cost_usd_total',
    'Total LLM cost in USD',
    ['task_type', 'model']
)

llm_latency = Histogram(
    'llm_latency_seconds',
    'LLM call latency',
    ['task_type', 'model']
)

llm_quality = Gauge(
    'llm_quality_score',
    'LLM response quality score',
    ['task_type', 'scenario']
)

class MetricsCollector:
    """Prometheus 指标收集器"""
    
    def record_llm_call(self, data: Dict):
        """记录 LLM 调用指标"""
        # Token 使用
        token_usage.labels(
            task_type=data["task_type"],
            token_type="input"
        ).inc(data["input_tokens"])
        
        token_usage.labels(
            task_type=data["task_type"],
            token_type="output"
        ).inc(data["output_tokens"])
        
        # 成本
        llm_cost.labels(
            task_type=data["task_type"],
            model=data["model"]
        ).inc(data["cost_usd"])
        
        # 延迟
        llm_latency.labels(
            task_type=data["task_type"],
            model=data["model"]
        ).observe(data["latency_ms"] / 1000)  # 转换为秒
```

**选项 B: 使用 InfluxDB**

```python
# app/services/metrics_collector.py

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

class InfluxMetricsCollector:
    """InfluxDB 指标收集器"""
    
    def __init__(self, url: str, token: str, org: str, bucket: str):
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.bucket = bucket
        self.org = org
    
    def record_llm_call(self, data: Dict):
        """记录 LLM 调用指标"""
        point = Point("llm_call") \
            .tag("task_type", data["task_type"]) \
            .tag("model", data["model"]) \
            .tag("provider", data["provider"]) \
            .field("input_tokens", data["input_tokens"]) \
            .field("output_tokens", data["output_tokens"]) \
            .field("total_tokens", data["total_tokens"]) \
            .field("cost_usd", data["cost_usd"]) \
            .field("latency_ms", data["latency_ms"]) \
            .time(datetime.now())
        
        self.write_api.write(bucket=self.bucket, org=self.org, record=point)
```

---

### 步骤 3: 配置 Grafana 仪表板

**仪表板配置 (JSON)**:

```json
{
  "dashboard": {
    "title": "LLM Token Optimization Dashboard",
    "panels": [
      {
        "title": "Token Usage Over Time",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(llm_tokens_total[5m])",
            "legendFormat": "{{task_type}} - {{token_type}}"
          }
        ]
      },
      {
        "title": "Cost Per Hour",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(llm_cost_usd_total[1h])",
            "legendFormat": "{{task_type}}"
          }
        ]
      },
      {
        "title": "Average Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, llm_latency_seconds)",
            "legendFormat": "P95 - {{task_type}}"
          }
        ]
      },
      {
        "title": "Token Reduction",
        "type": "stat",
        "targets": [
          {
            "expr": "(baseline_tokens - optimized_tokens) / baseline_tokens * 100"
          }
        ]
      }
    ]
  }
}
```

**关键面板**:

1. **Token 使用趋势**
   - 时间序列图
   - 按任务类型分组
   - 显示输入/输出 token

2. **成本监控**
   - 每小时成本
   - 每日成本累计
   - 成本预测

3. **性能指标**
   - P50/P95/P99 延迟
   - 错误率
   - 请求成功率

4. **优化效果**
   - Token 减少百分比
   - 成本节省金额
   - 质量对比

---

### 步骤 4: 设置告警规则

**Prometheus 告警规则**:

```yaml
# prometheus_alerts.yml

groups:
  - name: llm_optimization_alerts
    interval: 1m
    rules:
      # Token 使用过高
      - alert: HighTokenUsage
        expr: rate(llm_tokens_total[5m]) > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High token usage detected"
          description: "Token usage is {{ $value }} tokens/sec"
      
      # 成本过高
      - alert: HighCost
        expr: rate(llm_cost_usd_total[1h]) > 10
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "High LLM cost detected"
          description: "Cost is ${{ $value }}/hour"
      
      # 延迟过高
      - alert: HighLatency
        expr: histogram_quantile(0.95, llm_latency_seconds) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "P95 latency is {{ $value }}s"
      
      # 质量下降
      - alert: QualityDegradation
        expr: llm_quality_score < 0.8
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Quality degradation detected"
          description: "Quality score is {{ $value }}"
```

**告警通知配置**:

```yaml
# alertmanager.yml

route:
  receiver: 'team-email'
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: 'team-email'
    email_configs:
      - to: 'team@example.com'
        from: 'alerts@example.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'alerts@example.com'
        auth_password: 'password'
  
  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx'
        channel: '#llm-alerts'
        title: 'LLM Optimization Alert'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
```

---

### 步骤 5: 日志分析脚本

**每日报告生成**:

```python
# scripts/generate_daily_report.py

import asyncio
from datetime import datetime, timedelta
from scripts.analyze_trace import load_trace_file, extract_llm_calls

async def generate_daily_report():
    """生成每日报告"""
    
    # 加载今天的 trace 日志
    today = datetime.now().date()
    trace_file = f"logs/trace_{today}.jsonl"
    
    entries = load_trace_file(trace_file)
    llm_calls = extract_llm_calls(entries)
    
    # 计算统计数据
    total_tokens = sum(call["total_tokens"] for call in llm_calls)
    total_cost = sum(call["cost_usd"] for call in llm_calls)
    avg_latency = sum(call["latency_ms"] for call in llm_calls) / len(llm_calls)
    
    # 按任务类型分组
    by_task = {}
    for call in llm_calls:
        task = call["task_type"]
        if task not in by_task:
            by_task[task] = {
                "count": 0,
                "tokens": 0,
                "cost": 0
            }
        by_task[task]["count"] += 1
        by_task[task]["tokens"] += call["total_tokens"]
        by_task[task]["cost"] += call["cost_usd"]
    
    # 生成报告
    report = f"""
# LLM Token 优化 - 每日报告

**日期**: {today}

## 总体统计

- 总请求数: {len(llm_calls):,}
- 总 Token: {total_tokens:,}
- 总成本: ${total_cost:.2f}
- 平均延迟: {avg_latency:.0f}ms

## 按任务类型统计

| 任务类型 | 请求数 | Token | 成本 |
|---------|--------|-------|------|
"""
    
    for task, stats in by_task.items():
        report += f"| {task} | {stats['count']:,} | {stats['tokens']:,} | ${stats['cost']:.2f} |\n"
    
    # 保存报告
    report_file = f"reports/daily_report_{today}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"报告已生成: {report_file}")
    
    # 发送邮件（可选）
    await send_email_report(report)

if __name__ == "__main__":
    asyncio.run(generate_daily_report())
```

**定时任务配置 (cron)**:

```bash
# 每天凌晨 1 点生成报告
0 1 * * * cd /path/to/project && python scripts/generate_daily_report.py

# 每小时检查告警
0 * * * * cd /path/to/project && python scripts/check_alerts.py
```

---

## 📈 监控指标详解

### Token 指标

```python
# 关键 Token 指标
metrics = {
    # 使用量
    "total_tokens": "总 token 数",
    "input_tokens": "输入 token 数",
    "output_tokens": "输出 token 数",
    
    # 效率
    "tokens_per_request": "每请求平均 token",
    "token_reduction_rate": "Token 减少率",
    
    # 分布
    "tokens_by_task": "按任务类型的 token 分布",
    "tokens_by_model": "按模型的 token 分布"
}
```

### 成本指标

```python
# 关键成本指标
metrics = {
    # 总成本
    "total_cost": "总成本 (USD)",
    "cost_per_request": "每请求成本",
    "cost_per_user": "每用户成本",
    
    # 趋势
    "daily_cost": "每日成本",
    "monthly_cost": "每月成本",
    "cost_trend": "成本趋势",
    
    # 节省
    "cost_savings": "成本节省",
    "savings_rate": "节省率"
}
```

### 质量指标

```python
# 关键质量指标
metrics = {
    # 评分
    "quality_score": "质量评分 (0-1)",
    "relevance_score": "相关性评分",
    "intimacy_check_pass_rate": "亲密度检查通过率",
    
    # 用户反馈
    "user_satisfaction": "用户满意度",
    "complaint_rate": "投诉率"
}
```

### 性能指标

```python
# 关键性能指标
metrics = {
    # 延迟
    "avg_latency": "平均延迟",
    "p95_latency": "P95 延迟",
    "p99_latency": "P99 延迟",
    
    # 可靠性
    "success_rate": "成功率",
    "error_rate": "错误率",
    "timeout_rate": "超时率"
}
```

---

## 🎯 监控最佳实践

### 1. 分层监控

```
应用层监控
├── Token 使用
├── 成本
└── 质量

基础设施监控
├── CPU/内存
├── 网络
└── 磁盘

业务监控
├── 用户活跃度
├── 转化率
└── 留存率
```

### 2. 告警策略

**告警级别**:
- **Critical**: 立即处理（质量下降、成本失控）
- **Warning**: 需要关注（Token 使用偏高）
- **Info**: 仅记录（配置变更）

**告警降噪**:
- 设置合理的阈值
- 使用告警分组
- 避免告警风暴

### 3. 数据保留

```python
# 数据保留策略
retention_policy = {
    "raw_logs": "7 天",      # 原始日志
    "hourly_metrics": "30 天",  # 小时级指标
    "daily_metrics": "1 年",    # 日级指标
    "monthly_metrics": "永久"   # 月级指标
}
```

---

## ✅ 验证清单

### 监控系统
- [ ] Trace 日志正常记录
- [ ] 指标收集器运行正常
- [ ] 时序数据库连接正常
- [ ] Grafana 仪表板可访问

### 告警系统
- [ ] 告警规则配置完成
- [ ] 告警通知渠道测试通过
- [ ] 告警降噪规则生效
- [ ] 值班人员已培训

### 报告系统
- [ ] 每日报告自动生成
- [ ] 报告内容准确完整
- [ ] 报告发送正常
- [ ] 报告存档正常

---

## 📚 参考资料

- Prometheus 文档: https://prometheus.io/docs/
- Grafana 文档: https://grafana.com/docs/
- InfluxDB 文档: https://docs.influxdata.com/
- Phase 3 完成报告: `PHASE3_COMPLETION_REPORT.md`

---

**创建日期**: 2026-01-22  
**最后更新**: 2026-01-22  
**版本**: 1.0
