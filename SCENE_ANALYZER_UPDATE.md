# 场景分析器更新文档

## 概述

根据新增的 `SCENARIO_PROMPT`，完善了 `app/services/scene_analyzer_impl.py` 的设计，使其能够分析对话场景并给出推荐的情景和策略。场景分析器现在能够根据用户设置的亲密度和当前分析的亲密度计算关系状态和风险标记。

## 修改内容

### 1. 更新 `SceneAnalysisInput` (app/models/schemas.py)

添加了以下字段：
- `history_topic_summary: str` - 历史对话话题总结
- `current_conversation_summary: str` - 当前对话总结  
- `current_conversation: list[Message]` - 当前对话
- `intimacy_value: int` - 用户设置的亲密度 (0-101)
- `current_intimacy_level: int` - 当前分析的亲密度 (0-101)

### 2. 更新 `SceneAnalysisResult` (app/models/schemas.py)

添加了以下字段：
- `current_scenario: str` - 当前情景（安全/低风险策略|平衡/中风险策略|高风险/高回报策略|关系修复策略|禁止的策略）
- `recommended_scenario: str` - 推荐情景
- `recommended_strategies: list[str]` - 推荐的对话策略（3个策略代码）

更新了字段含义：
- `relationship_state` - 基于亲密度差异计算（破冰/推进/冷却/维持）
- `risk_flags` - 基于亲密度差异生成的风险标记
- `intimacy_level` - 使用用户设置的亲密度
- `scenario` - 使用推荐场景（从 recommended_scenario 获取）

### 3. 完善 `SceneAnalyzer` (app/services/scene_analyzer_impl.py)

#### 主要功能：
- 使用 LLM 分析对话场景
- 识别当前使用的策略类型
- 推荐适合的情景和具体策略
- **根据亲密度差异计算关系状态**
- **根据亲密度差异生成风险标记**

#### 核心方法：

**`analyze_scene(input: SceneAnalysisInput) -> SceneAnalysisResult`**
- 调用 LLM 使用 `SCENARIO_PROMPT` 分析对话
- 解析 LLM 返回的 JSON 结果
- 计算 relationship_state 和 risk_flags
- 返回包含当前情景、推荐情景和推荐策略的结果

**`_calculate_relationship_state(intimacy_value: int, current_intimacy_level: int) -> str`**
- 根据用户设置的亲密度和当前亲密度计算关系状态
- 差值 > 10: 返回 "破冰"（低亲密度）或 "推进"（中高亲密度）
- 差值 < -10: 返回 "冷却"
- 差值在 -10 到 10 之间: 返回 "维持"

**`_calculate_risk_flags(intimacy_value: int, current_intimacy_level: int) -> list[str]`**
- 根据亲密度差异计算风险标记
- 差值 > 20: ["期望过高", "需要循序渐进"]
- 差值 < -20: ["关系倒退", "需要修复关系"]
- 低亲密度但期望很高: ["跨度过大"]
- 高亲密度但期望降低: ["关系危机"]

**`_format_conversation(input: SceneAnalysisInput) -> str`**
- 格式化对话内容为 LLM prompt
- 包含历史话题总结、当前对话总结和当前对话详情

**`_parse_response(response_text: str) -> dict`**
- 解析 LLM 返回的 JSON
- 处理 markdown 代码块
- 提供默认值以应对解析失败

### 4. 更新 Orchestrator (app/services/orchestrator.py)

**`_analyze_scene(request, context)`**
- 传递 `context` 参数以获取当前亲密度
- 使用 `request.intimacy_value` 作为用户设置的亲密度
- 使用 `context.current_intimacy_level` 作为当前分析的亲密度

**`_infer_persona(request, scene)`**
- 使用 `scene.recommended_scenario` 而不是 `scene.scenario`

### 5. 更新 Reply Generator (app/services/reply_generator_impl.py)

**集成推荐策略到回复生成**
- 提取 `scene.recommended_strategies` 并传递给 prompt
- 提取 `scene.current_scenario` 和 `scene.recommended_scenario`
- 在 CHATCOACH_PROMPT 中强调使用推荐的策略

### 6. 更新 CHATCOACH_PROMPT (app/services/prompt.py)

**增强 prompt 结构**
- 添加"当前场景"和"推荐场景"部分
- 添加"推荐策略"部分
- 在任务说明中强调优先使用推荐的策略
- 保持语言参数的使用

## 策略分类体系

根据 `SCENARIO_PROMPT`，系统支持以下策略类型：

### 1. 安全/低风险策略 (Safe/Low Risk)
适用于陌生阶段，低容错，保守互动。
示例策略：
- `situational_comment` - 情境评论
- `light_humor` - 轻松幽默
- `neutral_open_question` - 中性开放问题
- `empathetic_ack` - 共情回应
- `pace_matching` - 节奏匹配

### 2. 平衡/中风险策略 (Balance/Medium Risk)
适用于关系推进阶段，风险可控。
示例策略：
- `playful_tease` - 善意调侃
- `direct_compliment` - 直接赞美
- `emotional_resonance` - 情绪共鸣
- `story_snippet` - 故事片段
- `curiosity_hook` - 好奇心钩子

### 3. 高风险/高回报策略 (Risky/High Reward)
适用于关系亲密，高容错。
示例策略：
- `sexual_hint` - 性暗示
- `dominant_lead` - 主导引领
- `bold_assumption` - 大胆假设

### 4. 关系修复策略 (Recovery/Repair)
适用于关系出现裂痕后的修复。
示例策略：
- `tension_release` - 缓解尴尬
- `boundary_respect` - 明确退回
- `misstep_repair` - 承认失误

### 5. 禁止的策略 (Negative/Anti-pattern)
不应该使用的策略。
示例：
- `validation_seeking` - 寻求认可
- `over_explaining` - 过度解释
- `neediness_signal` - 需求感信号

## 关系状态和风险标记的区别

### relationship_state（关系状态）
- **目的**: 描述关系的发展方向
- **计算依据**: 用户期望亲密度 vs 当前亲密度的差异
- **取值**: "破冰"、"推进"、"冷却"、"维持"
- **用途**: 指导整体互动策略

### risk_flags（风险标记）
- **目的**: 识别潜在的关系风险
- **计算依据**: 亲密度差异的大小和方向
- **取值**: 列表，如 ["期望过高", "需要循序渐进"]
- **用途**: 提醒需要注意的风险点

### current_scenario（当前情景）
- **目的**: 描述当前对话中使用的策略类型
- **计算依据**: LLM 分析对话内容
- **取值**: "安全/低风险策略"、"平衡/中风险策略"等
- **用途**: 了解当前对话风格

### recommended_scenario（推荐情景）
- **目的**: 建议下一步应该使用的策略类型
- **计算依据**: LLM 综合分析对话和关系状态
- **取值**: "安全/低风险策略"、"平衡/中风险策略"等
- **用途**: 指导回复生成

## 使用示例

```python
from app.models.schemas import SceneAnalysisInput, Message
from app.services.scene_analyzer_impl import SceneAnalyzer
from app.services.llm_adapter import LLMAdapterImpl

# 初始化
llm_adapter = LLMAdapterImpl()
scene_analyzer = SceneAnalyzer(llm_adapter, provider="dashscope", model="qwen-flash")

# 准备输入
messages = [
    Message(id="1", speaker="user", content="Hey, how are you?", timestamp=None),
    Message(id="2", speaker="Sarah", content="I'm good, thanks!", timestamp=None),
]

input_data = SceneAnalysisInput(
    conversation_id="conv_001",
    history_dialog=messages,
    history_topic_summary="初次接触，简单问候",
    current_conversation_summary="用户问候，对方礼貌回应",
    current_conversation=messages,
    intimacy_value=70,  # 用户期望的亲密度
    current_intimacy_level=30,  # 当前分析的亲密度
)

# 执行分析
result = await scene_analyzer.analyze_scene(input_data)

print(f"关系状态: {result.relationship_state}")  # "破冰"
print(f"当前情景: {result.current_scenario}")  # "安全/低风险策略"
print(f"推荐情景: {result.recommended_scenario}")  # "平衡/中风险策略"
print(f"推荐策略: {result.recommended_strategies}")  # ['playful_tease', 'emotional_resonance', 'curiosity_hook']
print(f"风险标记: {result.risk_flags}")  # ['期望过高', '需要循序渐进']
```

## 测试结果

测试脚本 `test_scene_analyzer.py` 验证了三种场景：

### 场景1: 用户期望亲密度(70) > 当前亲密度(30) - 需要推进
```
关系状态: 破冰
场景: 平衡/中风险策略
亲密度: 70
当前情景: 安全/低风险策略
推荐情景: 平衡/中风险策略
推荐策略: ['playful_tease', 'emotional_resonance', 'curiosity_hook']
风险标记: ['期望过高', '需要循序渐进']
```

### 场景2: 用户期望亲密度(30) < 当前亲密度(80) - 需要冷却
```
关系状态: 冷却
场景: 平衡/中风险策略
亲密度: 30
当前情景: 安全/低风险策略
推荐情景: 平衡/中风险策略
推荐策略: ['playful_tease', 'emotional_resonance', 'curiosity_hook']
风险标记: ['关系倒退', '需要修复关系']
```

### 场景3: 用户期望亲密度(50) ≈ 当前亲密度(48) - 维持
```
关系状态: 维持
场景: 平衡/中风险策略
亲密度: 50
当前情景: 安全/低风险策略
推荐情景: 平衡/中风险策略
推荐策略: ['playful_tease', 'emotional_resonance', 'curiosity_hook']
风险标记: []
```

## 集成说明

场景分析器已完全集成到 Orchestrator 流程中：
1. Context Builder 构建对话上下文（包含 current_intimacy_level）
2. **Scene Analyzer 分析场景并推荐策略**
   - 接收用户设置的亲密度和当前亲密度
   - 计算关系状态和风险标记
   - 使用 LLM 分析当前和推荐场景
   - 提供 3 个推荐策略代码
3. Persona Inferencer 推断用户画像（使用 recommended_scenario）
4. **Reply Generator 生成回复（使用推荐的策略）**
   - 接收 current_scenario、recommended_scenario 和 recommended_strategies
   - 在 prompt 中强调使用推荐的策略
5. Intimacy Checker 检查回复适当性

## 后续优化建议

1. **策略有效性追踪**
   - 记录使用的策略和对话结果
   - 分析哪些策略在特定场景下更有效

2. **动态策略调整**
   - 根据对话反馈实时调整推荐策略
   - 学习用户的策略偏好

3. **增强错误处理**
   - 添加重试机制
   - 提供更详细的错误日志

4. **性能优化**
   - 缓存相似对话的分析结果
   - 使用更快的模型进行初步分析

5. **多语言支持**
   - 支持不同语言的策略分析
   - 考虑文化差异对策略的影响

## 相关文件

- `app/models/schemas.py` - 数据模型定义
- `app/services/scene_analyzer_impl.py` - 场景分析器实现
- `app/services/orchestrator.py` - 编排器集成
- `app/services/reply_generator_impl.py` - 回复生成器集成
- `app/services/prompt.py` - SCENARIO_PROMPT 和 CHATCOACH_PROMPT 定义
- `test_scene_analyzer.py` - 测试脚本

## 更新日志

### 2024-01-19
- ✅ 添加亲密度计算逻辑（relationship_state 和 risk_flags）
- ✅ 集成推荐策略到回复生成器
- ✅ 更新 CHATCOACH_PROMPT 强调使用推荐策略
- ✅ 更新 Orchestrator 使用 recommended_scenario
- ✅ 完善测试脚本验证三种亲密度场景
- ✅ 更新文档说明各字段的区别和用途
