# Token 使用分析与优化建议

## 当前 Token 使用情况总结

基于 `logs/trace.jsonl` 的分析，以下是完整流程的 token 使用情况：

### 总览

| 步骤 | Task Type | Provider | Model | Input Tokens | Output Tokens | Total Tokens | Prompt Length (chars) |
|------|-----------|----------|-------|--------------|---------------|--------------|----------------------|
| 1. Learn Traits | persona | dashscope | qwen-flash | 311 | 603 | 914 | 1,291 |
| 2. Map Traits | persona | dashscope | qwen-flash | 494 | 559 | 1,053 | 1,939 |
| 3. Context Builder | scene | gemini | gemini-2.5-flash | 489 | 98 | 587 | 1,938 |
| 4. Scene Analysis | scene | dashscope | qwen-flash | 496 | 189 | 685 | 2,219 |
| 5. Reply Generation | generation | dashscope | qwen-flash | 832 | 473 | 1,305 | 3,591 |
| **总计** | - | - | - | **2,622** | **1,922** | **4,544** | **11,978** |

### 成本分析
- 总成本：$0.00（使用的是免费或低成本模型）
- 平均每次调用：909 tokens
- 最大单次调用：1,305 tokens（Reply Generation）

---

## 主要问题识别

### 1. **Reply Generation 步骤 Token 过高**
- **Input Tokens: 832**
- **Prompt Length: 3,591 字符**
- **问题**：包含了大量冗余信息
  - 完整的 User Profile（包含所有 learned traits 的详细描述）
  - 重复的对话历史
  - 过长的策略说明

### 2. **User Profile 信息冗余**
在 Reply Generation prompt 中，User Profile 包含：
```
- learned_traits/general/Narrative Engagement: {'trait_name': 'Narrative Engagement', 'description': 'A tendency to deeply engage with conceptual and abstract narratives...', 'evidence': "The user expresses fascination...", 'confidence': 0.92}
```
这些详细的 trait 描述占用了大量 tokens，但对生成回复的实际帮助有限。

### 3. **Scene Analysis Prompt 可以精简**
- **Input Tokens: 496**
- **Prompt Length: 2,219 字符**
- 包含了完整的策略分类体系说明（12种策略类型的详细描述）

### 4. **Context Builder 重复对话内容**
- 对话历史在多个步骤中重复传递
- 每次都完整格式化对话文本

---

## 优化建议

### 优先级 1：精简 Reply Generation Prompt（预计减少 40-50% tokens）

#### 1.1 简化 User Profile 表示
**当前：**
```python
- learned_traits/general/Narrative Engagement: {'trait_name': 'Narrative Engagement', 'description': 'A tendency to deeply engage with conceptual and abstract narratives, especially those exploring human cognition, societal structures, and collective belief systems.', 'evidence': "The user expresses fascination with the concept of 'collective imagination' from 'Sapiens', indicating a focus on how shared stories shape human cooperation, suggesting engagement with high-level theoretical frameworks.", 'confidence': 0.92}
```

**优化后：**
```python
- Traits: high_abstraction(0.92), reflective(0.88), intellectual_depth(0.85)
```

**预计节省：** ~300 tokens

#### 1.2 移除冗余的策略说明
当前 prompt 包含了完整的策略分类体系，但实际上只需要推荐的策略代码。

**优化：** 只传递 `recommended_strategies` 列表，不需要完整的策略说明文档。

**预计节省：** ~150 tokens

#### 1.3 精简对话历史格式
**当前：**
```
me: Hey Sarah, I noticed you have a photo with a copy of "Sapiens" on your bookshelf. Great book! What did you think of the author's take on collective imagination?
Sarah: Oh, wow, someone actually zoomed in! Most people just comment on the travel pics...
```

**优化后：**
```
U: Noticed "Sapiens" on shelf, asked about collective imagination
S: Surprised, discussed myths & cooperation, asked about sequel
U: Read it, felt anxious, complimented travel pics
...
```

**预计节省：** ~200 tokens

### 优先级 2：优化 Scene Analysis Prompt（预计减少 30% tokens）

#### 2.1 使用策略代码而非完整描述
**当前：** 包含所有策略的详细说明（2,219 字符）

**优化：** 只列出策略代码，将详细说明移到系统配置或文档中

**预计节省：** ~200 tokens

#### 2.2 使用对话摘要而非完整对话
已经有 `conversation_summary`，不需要再传递完整对话历史。

**预计节省：** ~150 tokens

### 优先级 3：优化 User Profile Learning（预计减少 20% tokens）

#### 3.1 Learn Traits - 精简输出格式
**当前输出：** 包含完整的 description 和 evidence

**优化：** 
- 在学习阶段保留完整信息（用于存储）
- 在使用阶段只传递关键信息（trait_name + confidence）

#### 3.2 Map Traits - 减少标准 trait 列表
**当前：** 列出 25 个标准 traits

**优化：** 只列出最相关的 10-15 个核心 traits

**预计节省：** ~100 tokens

---

## 具体实施方案

### 方案 1：创建精简的 Prompt 模板（推荐）

创建两套 prompt 模板：
1. **详细版**（用于调试和分析）
2. **精简版**（用于生产环境）

```python
# app/services/prompt_compact.py

CHATCOACH_PROMPT_COMPACT = """Professional dating coach. Generate 3 reply suggestions.

## Context
Scenario: {recommended_scenario}
Strategies: {recommended_strategies}
Intimacy: User({intimacy_level}) vs Current({current_intimacy_level})
Emotion: {emotion_state}

## Summary
{conversation_summary}

## User Style
{user_style_compact}  # 精简版：只包含关键 traits

## Last Message
{last_message}

## Language
{language}

Output JSON:
{{
  "replies": [
    {{"text": "...", "strategy": "...", "reasoning": "..."}},
    {{"text": "...", "strategy": "...", "reasoning": "..."}},
    {{"text": "...", "strategy": "...", "reasoning": "..."}}
  ]
}}
"""
```

### 方案 2：实现 Token 预算管理

```python
# app/services/token_manager.py

class TokenBudget:
    """Manage token budget for prompts"""
    
    MAX_TOKENS = {
        "context_builder": 600,
        "scene_analysis": 700,
        "reply_generation": 1000,
    }
    
    def truncate_conversation(self, messages, max_tokens):
        """Truncate conversation to fit token budget"""
        # 保留最近的消息
        # 或使用摘要替代旧消息
        pass
    
    def compress_user_profile(self, profile, max_tokens):
        """Compress user profile to essential info"""
        # 只保留 top-N traits
        # 移除 evidence 和详细 description
        pass
```

### 方案 3：使用对话摘要缓存

```python
# app/services/conversation_cache.py

class ConversationCache:
    """Cache conversation summaries to avoid re-processing"""
    
    def get_summary(self, conversation_id, messages):
        """Get cached summary or generate new one"""
        cache_key = self._hash_messages(messages)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Generate new summary
        summary = self._generate_summary(messages)
        self.cache[cache_key] = summary
        return summary
```

---

## 预期效果

### Token 减少预估

| 步骤 | 当前 Input Tokens | 优化后 Input Tokens | 减少比例 |
|------|-------------------|---------------------|----------|
| Context Builder | 489 | 350 | -28% |
| Scene Analysis | 496 | 350 | -29% |
| Reply Generation | 832 | 450 | -46% |
| **总计** | **2,622** | **1,500** | **-43%** |

### 成本节省
- 如果使用付费 API（如 GPT-4），每次完整流程可节省约 **43% 的成本**
- 对于高频使用场景，年度成本可节省数千美元

### 性能提升
- 更少的 tokens = 更快的响应时间
- 减少网络传输时间
- 降低 API 限流风险

---

## 实施优先级

### 阶段 1：立即实施（1-2天）
1. ✅ 精简 Reply Generation 中的 User Profile 表示
2. ✅ 移除 Scene Analysis 中的完整策略说明
3. ✅ 使用对话摘要替代完整对话历史

**预期效果：** 减少 30-40% tokens

### 阶段 2：短期优化（1周）
1. 创建精简版 prompt 模板
2. 实现 token 预算管理器
3. 添加对话摘要缓存

**预期效果：** 再减少 10-15% tokens

### 阶段 3：长期优化（持续）
1. 使用更小的模型处理简单任务
2. 实现智能 prompt 压缩
3. A/B 测试不同 prompt 版本的效果

**预期效果：** 持续优化，保持最佳性价比

---

## 监控指标

建议添加以下监控指标：

```python
# app/services/metrics.py

class TokenMetrics:
    """Track token usage metrics"""
    
    def record_call(self, task_type, input_tokens, output_tokens, cost):
        """Record token usage for analysis"""
        self.metrics[task_type].append({
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost": cost,
            "timestamp": datetime.now(),
        })
    
    def get_stats(self, task_type=None):
        """Get token usage statistics"""
        # 返回平均值、最大值、最小值、趋势等
        pass
```

---

## 注意事项

### 1. 质量 vs 成本权衡
- 过度精简可能影响生成质量
- 建议先在测试环境验证效果
- 保留详细版 prompt 用于对比

### 2. 不同场景的优化策略
- **高频简单场景**：使用最精简版本
- **复杂关键场景**：使用详细版本
- **调试阶段**：使用详细版本

### 3. 渐进式优化
- 不要一次性改动太大
- 每次优化后测试生成质量
- 记录优化前后的对比数据

---

## 下一步行动

1. **立即行动**：
   - [ ] 创建 `app/services/prompt_compact.py`
   - [ ] 实现精简版 User Profile 序列化
   - [ ] 更新 Reply Generator 使用精简 prompt

2. **本周完成**：
   - [ ] 添加 token 使用监控
   - [ ] 实现对话摘要缓存
   - [ ] A/B 测试精简版 vs 详细版

3. **持续优化**：
   - [ ] 定期审查 token 使用趋势
   - [ ] 根据实际效果调整策略
   - [ ] 探索更高效的模型选择

---

## 参考资料

- [OpenAI Token Counting](https://platform.openai.com/tokenizer)
- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [LangChain Token Management](https://python.langchain.com/docs/modules/model_io/prompts/prompt_templates/)
