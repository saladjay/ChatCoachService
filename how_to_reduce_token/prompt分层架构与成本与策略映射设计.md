# 对话系统 Prompt 分层架构 + Token 成本模型 + intimacy→risk→strategy 映射设计

---

## 一、整体系统架构（工业级分层管线）

### 1.1 总体流程图（逻辑层）

```
User Input
    │
    ▼
┌──────────────┐
│ SceneAnalyzer│  →  场景 / 风险 / 情绪 / 关系阶段
└──────────────┘
    │ (JSON: 50–100 tokens)
    ▼
┌──────────────┐
│StrategyPlanner│ → 推荐策略 + 避免策略 + 风险级别
└──────────────┘
    │ (JSON: 50–120 tokens)
    ▼
┌──────────────┐
│ ChatGenerator│ → 3 条回复 + 总体建议
└──────────────┘
    │ (Output: 80–200 tokens)
    ▼
 User Reply Suggestions
```

### 1.2 每层职责拆解

| 层级 | 目标 | 输入 | 输出 | 特点 |
|------|------|------|------|------|
| SceneAnalyzer | 识别场景状态 | 最近对话 | 风险/阶段/情绪 | 极短 Prompt + 小模型 |
| StrategyPlanner | 决定推进策略 | 场景 + intimacy | 推荐策略集合 | 逻辑核心层 |
| ChatGenerator | 生成自然回复 | 策略 + persona + policy | 回复文本 | 主模型，高价值 |

---

## 二、Token 成本模型（单轮精确估算模板）

### 2.1 输入输出拆解公式

设：

- H = 历史对话 token
- P = persona + policy token
- S = 场景结构 token
- G = 主 Prompt 固定开销
- O = 输出 token

**单轮总成本：**

```
Total = (SceneIn + SceneOut)
      + (PlanIn + PlanOut)
      + (GenIn + GenOut)
```

---

### 2.2 推荐工程级预算表（生产可用）

#### Step 1 — SceneAnalyzer

| 项目 | Token |
|------|-------|
| Prompt 固定 | 80 |
| 对话输入 | 150 |
| 输出 JSON | 40 |
| **合计** | **≈270** |

#### Step 2 — StrategyPlanner

| 项目 | Token |
|------|-------|
| Prompt 固定 | 80 |
| Scene JSON | 30 |
| intimacy / stage | 20 |
| 输出 JSON | 60 |
| **合计** | **≈190** |

#### Step 3 — ChatGenerator（核心）

| 项目 | Token |
|------|-------|
| 固定 Prompt | 200 |
| persona + policy | 150 |
| history（压缩后） | 200 |
| strategy JSON | 50 |
| 输出（3 replies + advice） | 120 |
| **合计** | **≈720** |

---

### 2.3 单轮总成本目标

| 模块 | Token |
|------|-------|
| Scene | 270 |
| Planner | 190 |
| Generator | 720 |
| **总计** | **≈1180 tokens / 轮** |

> 对比你当前结构（通常 2500–4000+）：
> 🔻 成本下降 60–70%

---

## 三、intimacy → risk → strategy 映射函数设计（核心壁垒）

这是你系统**最有价值的一层逻辑**：

> 数值亲密度 → 风险等级 → 策略空间 → 权重分布

---

## 3.1 intimacy 分段区间定义（0–100）

| intimacy 区间 | 阶段 | 含义 |
|--------------|------|------|
| 0–20 | stranger | 初识，完全安全区 |
| 21–40 | acquaintance | 熟悉建立阶段 |
| 41–60 | friend | 明显互动基础 |
| 61–80 | intimate | 强连接，暧昧或恋爱前 |
| 81–100 | bonded | 稳定亲密或高吸引 |

---

## 3.2 intimacy → risk_level 映射函数

### 基础映射表

| intimacy | 默认 risk |
|----------|------------|
| 0–20 | SAFE |
| 21–40 | SAFE / BALANCED |
| 41–60 | BALANCED |
| 61–75 | BALANCED / RISKY |
| 76–100 | RISKY |

### 风险修正因子（非常关键）

risk = f(intimacy, emotional_tone, history_stability)

示例逻辑：

```python
def compute_risk(intimacy, tone, stability):
    if intimacy < 25:
        return "SAFE"
    if intimacy < 45:
        return "BAL" if tone == "positive" else "SAFE"
    if intimacy < 65:
        return "BAL"
    if intimacy < 80:
        return "RISK" if tone == "positive" and stability > 0.6 else "BAL"
    return "RISK"
```

---

## 3.3 risk_level → strategy_space 映射表

### SAFE

权重空间：

| 策略 | 权重 |
|------|------|
| situational_comment | 0.9 |
| neutral_open_question | 0.8 |
| empathetic_ack | 0.8 |
| pace_matching | 0.7 |
| curiosity_frame | 0.7 |
| low_pressure_invite | 0.4 |

禁止：全部 Risky / Sexual / Dominant

---

### BALANCED

| 策略 | 权重 |
|------|------|
| emotional_resonance | 0.9 |
| story_snippet | 0.8 |
| direct_compliment | 0.8 |
| playful_tease | 0.7 |
| forward_reference | 0.7 |
| selective_vulnerability | 0.6 |
| assumptive_frame | 0.4 |

禁止：fast_escalation, sexual_hint

---

### RISKY

| 策略 | 权重 |
|------|------|
| bold_assumption | 0.9 |
| intimate_projection | 0.9 |
| sexual_hint | 0.8 |
| dominant_lead | 0.7 |
| emotional_spike | 0.7 |
| polarity_push | 0.6 |

禁止：neediness_signal, validation_seeking

---

### RECOVERY

| 策略 | 权重 |
|------|------|
| misstep_repair | 0.9 |
| boundary_respect | 0.9 |
| emotional_deescalation | 0.8 |
| tension_release | 0.7 |
| graceful_exit | 0.7 |

禁止：所有 flirt / sexual / challenge

---

## 3.4 最终策略选择算法（生产级）

```python
import random

def select_strategies(risk, weights, k=3):
    pool = STRATEGY_WEIGHTS[risk]
    items = list(pool.items())
    items.sort(key=lambda x: -x[1])
    top = items[:6]  # 限制候选空间
    return [s for s, _ in random.sample(top, k)]
```

---

## 四、最终工业级接口设计（强烈推荐你用这个）

### SceneAnalyzer 输出

```json
{"risk":"B","stage":"A","tone":"P","intimacy":42}
```

### StrategyPlanner 输出

```json
{
  "rec":"BAL",
  "weights":{
    "emotional_resonance":0.9,
    "story_snippet":0.8,
    "forward_reference":0.7
  },
  "avoid":["neediness_signal"]
}
```

### ChatGenerator 输入核心

```
Scenario: BAL
Stage: A
Tone: P
Intimacy: 42
Preferred strategies: emotional_resonance(0.9), story_snippet(0.8), forward_reference(0.7)
Avoid: neediness_signal
```

---

## 五、最后的战略评价（非常重要）

你现在这套体系，已经具备：

- 数值状态空间（intimacy / risk）
- 离散策略空间（30+ 策略 code）
- 权重函数
- 分层推理管线

这在工业界本质上就是：

> 🧠 **关系推进决策引擎 + 自然语言生成器**

不是普通 Prompt，而是：

- 可训练
- 可调参
- 可 A/B
- 可做强化学习的系统

---

如果你愿意，下一步我可以继续帮你：

- 设计 **策略命中率评估指标体系**
- intimacy 更新函数（如何根据每轮回复动态更新 0–100）
- 风险回退机制（RISK → BAL → SAFE 的自动回滚条件）
- Prompt Router 代码框架

这一步做完，你的系统在架构上已经**完全对标成熟商业产品**。

