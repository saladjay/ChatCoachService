# Phase 4: 内存压缩 (Memory Compression)

**目标**: 压缩对话历史，减少 70% 历史 token  
**预计时间**: 1 周  
**优先级**: ⭐⭐ 中高

---

## 📋 概述

长对话历史会消耗大量 token。Phase 4 通过智能压缩技术，将历史对话转换为紧凑的记忆表示，同时保持关键信息。

---

## 🎯 目标

### 主要目标
1. **减少历史 token 使用**
   - 目标: 70% 减少
   - 保持上下文质量
   - 不丢失关键信息

2. **智能信息提取**
   - 提取关键话题
   - 分析情感趋势
   - 识别重要事件

3. **高效存储**
   - 紧凑的内存格式
   - 快速检索
   - 易于更新

---

## 🏗️ 架构设计

### 组件结构

```
ConversationMemoryService
├── compress_history()          # 压缩对话历史
├── extract_topics()            # 提取话题
├── analyze_tone_trend()        # 分析情感趋势
├── analyze_style()             # 分析对话风格
└── format_memory_for_prompt()  # 格式化为 prompt
```

### 数据流

```
原始对话 (100 条消息, ~2000 tokens)
    ↓
提取关键信息
    ↓
压缩为记忆 (~600 tokens, -70%)
    ↓
格式化为 prompt
    ↓
与最近消息结合 (10 条, ~200 tokens)
    ↓
总计: ~800 tokens (vs 原始 2000 tokens)
```

---

## 💾 内存格式设计

### 压缩记忆结构

```python
@dataclass
class ConversationMemory:
    """压缩的对话记忆"""
    
    # 基本信息
    conversation_id: str
    user_id: str
    target_id: str
    
    # 时间范围
    start_time: datetime
    end_time: datetime
    message_count: int
    
    # 关键话题 (最多 5 个)
    topics: List[str]  # ["约会计划", "工作压力", "兴趣爱好"]
    
    # 情感趋势
    tone_trend: str  # "positive → neutral → positive"
    
    # 关键事件 (最多 3 个)
    key_events: List[str]  # ["用户提到明天有约会", "讨论了工作问题"]
    
    # 对话风格
    user_style: str  # "casual, friendly, open"
    target_style: str  # "supportive, empathetic"
    
    # 亲密度变化
    intimacy_change: str  # "50 → 65 (+15)"
    
    # 压缩统计
    original_tokens: int  # 2000
    compressed_tokens: int  # 600
    compression_ratio: float  # 0.70
```

### Prompt 格式

```
对话记忆 (过去 100 条消息):
- 时间: 2026-01-15 至 2026-01-22
- 话题: 约会计划, 工作压力, 兴趣爱好
- 情感: 积极 → 中性 → 积极
- 关键事件:
  * 用户提到明天有第一次约会，感到紧张
  * 讨论了如何处理工作压力
  * 分享了共同的兴趣爱好
- 风格: 用户轻松友好，对方支持共情
- 亲密度: 50 → 65 (+15)

最近对话 (最后 10 条消息):
[完整的最近消息]
```

---

## 🔧 实现细节

### 1. 话题提取

```python
async def extract_topics(self, messages: List[Message]) -> List[str]:
    """提取对话中的关键话题
    
    使用 LLM 分析对话内容，提取最多 5 个关键话题。
    
    Args:
        messages: 对话消息列表
    
    Returns:
        话题列表，按重要性排序
    """
    # 构建紧凑的 prompt
    conversation_text = self._format_messages_compact(messages)
    
    prompt = f"""分析以下对话，提取 3-5 个关键话题。
每个话题用 2-4 个词描述。

对话:
{conversation_text}

输出格式 (JSON):
{{"topics": ["话题1", "话题2", "话题3"]}}
"""
    
    # 调用 LLM (使用 cheap 模型)
    result = await self.llm_adapter.call(LLMCall(
        task_type="topic_extraction",
        prompt=prompt,
        quality="cheap",
        max_tokens=100
    ))
    
    # 解析结果
    data = json.loads(result.text)
    return data["topics"][:5]
```

### 2. 情感趋势分析

```python
async def analyze_tone_trend(self, messages: List[Message]) -> str:
    """分析对话的情感趋势
    
    将对话分为 3 段，分析每段的情感，返回趋势描述。
    
    Args:
        messages: 对话消息列表
    
    Returns:
        情感趋势描述，如 "positive → neutral → positive"
    """
    # 将消息分为 3 段
    segment_size = len(messages) // 3
    segments = [
        messages[:segment_size],
        messages[segment_size:segment_size*2],
        messages[segment_size*2:]
    ]
    
    tones = []
    for segment in segments:
        # 分析每段的情感
        tone = await self._analyze_segment_tone(segment)
        tones.append(tone)
    
    # 格式化趋势
    return " → ".join(tones)
```

### 3. 关键事件提取

```python
async def extract_key_events(self, messages: List[Message]) -> List[str]:
    """提取对话中的关键事件
    
    识别重要的转折点、决定、或重要信息。
    
    Args:
        messages: 对话消息列表
    
    Returns:
        关键事件列表 (最多 3 个)
    """
    conversation_text = self._format_messages_compact(messages)
    
    prompt = f"""识别对话中的关键事件或重要信息。
每个事件用一句话描述 (10-15 词)。

对话:
{conversation_text}

输出格式 (JSON):
{{"events": ["事件1", "事件2", "事件3"]}}
"""
    
    result = await self.llm_adapter.call(LLMCall(
        task_type="event_extraction",
        prompt=prompt,
        quality="cheap",
        max_tokens=150
    ))
    
    data = json.loads(result.text)
    return data["events"][:3]
```

### 4. 压缩历史

```python
async def compress_history(
    self,
    conversation_id: str,
    messages: List[Message],
    keep_recent: int = 10
) -> ConversationMemory:
    """压缩对话历史
    
    将长对话历史压缩为紧凑的记忆表示。
    
    Args:
        conversation_id: 对话 ID
        messages: 完整的消息列表
        keep_recent: 保留最近的消息数量
    
    Returns:
        压缩的对话记忆
    """
    # 分离历史和最近消息
    if len(messages) <= keep_recent:
        # 消息太少，不需要压缩
        return None
    
    history_messages = messages[:-keep_recent]
    
    # 并行提取信息
    topics_task = self.extract_topics(history_messages)
    tone_task = self.analyze_tone_trend(history_messages)
    events_task = self.extract_key_events(history_messages)
    style_task = self.analyze_style(history_messages)
    
    topics, tone_trend, key_events, styles = await asyncio.gather(
        topics_task, tone_task, events_task, style_task
    )
    
    # 计算亲密度变化
    intimacy_change = self._calculate_intimacy_change(history_messages)
    
    # 估算 token 数
    original_tokens = self._estimate_tokens(history_messages)
    compressed_tokens = self._estimate_compressed_tokens(
        topics, tone_trend, key_events, styles, intimacy_change
    )
    
    # 创建记忆对象
    memory = ConversationMemory(
        conversation_id=conversation_id,
        user_id=history_messages[0].user_id,
        target_id=history_messages[0].target_id,
        start_time=history_messages[0].timestamp,
        end_time=history_messages[-1].timestamp,
        message_count=len(history_messages),
        topics=topics,
        tone_trend=tone_trend,
        key_events=key_events,
        user_style=styles["user"],
        target_style=styles["target"],
        intimacy_change=intimacy_change,
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        compression_ratio=(original_tokens - compressed_tokens) / original_tokens
    )
    
    return memory
```

### 5. 格式化为 Prompt

```python
def format_memory_for_prompt(self, memory: ConversationMemory) -> str:
    """将压缩记忆格式化为 prompt
    
    Args:
        memory: 压缩的对话记忆
    
    Returns:
        格式化的 prompt 文本
    """
    if memory is None:
        return ""
    
    lines = [
        f"对话记忆 (过去 {memory.message_count} 条消息):",
        f"- 时间: {memory.start_time.strftime('%Y-%m-%d')} 至 {memory.end_time.strftime('%Y-%m-%d')}",
        f"- 话题: {', '.join(memory.topics)}",
        f"- 情感: {memory.tone_trend}",
        "- 关键事件:"
    ]
    
    for event in memory.key_events:
        lines.append(f"  * {event}")
    
    lines.extend([
        f"- 风格: 用户{memory.user_style}，对方{memory.target_style}",
        f"- 亲密度: {memory.intimacy_change}",
        ""
    ])
    
    return "\n".join(lines)
```

---

## 🔗 集成到现有系统

### 更新 ContextBuilder

```python
class ContextBuilder(BaseContextBuilder):
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        memory_service: ConversationMemoryService,  # 新增
        use_compact_prompt: bool = True
    ):
        self.llm_adapter = llm_adapter
        self.memory_service = memory_service  # 新增
        self.use_compact_prompt = use_compact_prompt
    
    async def build_context(
        self,
        user_id: str,
        conversation: List[Message],
        **kwargs
    ) -> ContextResult:
        # 压缩历史
        memory = await self.memory_service.compress_history(
            conversation_id=kwargs.get("conversation_id"),
            messages=conversation,
            keep_recent=10
        )
        
        # 获取最近消息
        recent_messages = conversation[-10:]
        
        # 构建 prompt (使用记忆 + 最近消息)
        if memory:
            memory_text = self.memory_service.format_memory_for_prompt(memory)
            recent_text = self._format_recent_messages(recent_messages)
            full_context = f"{memory_text}\n最近对话:\n{recent_text}"
        else:
            full_context = self._format_recent_messages(recent_messages)
        
        # 继续原有的上下文构建逻辑
        # ...
```

---

## 📊 预期效果

### Token 减少

| 场景 | 原始 Token | 压缩后 Token | 减少 |
|------|-----------|-------------|------|
| 短对话 (< 10 条) | 200 | 200 | 0% |
| 中等对话 (10-50 条) | 1,000 | 400 | 60% |
| 长对话 (50-100 条) | 2,000 | 600 | 70% |
| 超长对话 (> 100 条) | 4,000 | 800 | 80% |

### 成本影响

假设每天 10,000 个请求，平均对话长度 50 条：
- 原始成本: 10,000 × $0.010 = $100/天
- 压缩后成本: 10,000 × $0.004 = $40/天
- **节省: $60/天 = $1,800/月 = $21,900/年**

---

## 🧪 测试策略

### 单元测试

```python
# tests/test_conversation_memory.py

class TestConversationMemory:
    def test_topic_extraction(self):
        """测试话题提取"""
        # 测试能否正确提取话题
        
    def test_tone_analysis(self):
        """测试情感分析"""
        # 测试能否正确分析情感趋势
        
    def test_compression_ratio(self):
        """测试压缩比例"""
        # 验证压缩比例达到 70%
        
    def test_information_preservation(self):
        """测试信息保留"""
        # 验证关键信息没有丢失
```

### 集成测试

```python
# tests/integration/test_memory_compression.py

async def test_long_conversation_compression():
    """测试长对话压缩"""
    # 创建 100 条消息的对话
    messages = create_test_messages(100)
    
    # 压缩
    memory = await memory_service.compress_history(
        conversation_id="test",
        messages=messages
    )
    
    # 验证
    assert memory.compression_ratio >= 0.70
    assert len(memory.topics) <= 5
    assert len(memory.key_events) <= 3
```

---

## ⚠️ 注意事项

### 信息丢失风险
- **问题**: 压缩可能丢失重要细节
- **缓解**: 保留最近 10 条完整消息
- **验证**: 人工评估压缩质量

### LLM 调用成本
- **问题**: 压缩需要额外的 LLM 调用
- **缓解**: 使用 cheap 模型，批量处理
- **优化**: 缓存压缩结果

### 延迟影响
- **问题**: 压缩增加响应时间
- **缓解**: 异步压缩，后台处理
- **优化**: 增量更新记忆

---

## 📅 实施计划

### Week 1: 核心实现
- Day 1-2: 创建 `ConversationMemoryService`
- Day 3-4: 实现压缩算法
- Day 5: 集成到 `ContextBuilder`

### Week 2: 测试与优化
- Day 1-2: 单元测试
- Day 3-4: 集成测试
- Day 5: 性能优化

### Week 3: 验证与部署
- Day 1-2: 本地验证
- Day 3-5: 金丝雀部署
- Day 6-7: 全量部署

---

## 🎯 成功标准

- ✅ 历史 token 减少 ≥ 70%
- ✅ 关键信息保留率 ≥ 95%
- ✅ 压缩延迟 < 500ms
- ✅ 回复质量无下降
- ✅ 所有测试通过

---

## 📚 参考资料

- Phase 3 完成报告: `PHASE3_COMPLETION_REPORT.md`
- 实施清单: `how_to_reduce_token/IMPLEMENTATION_CHECKLIST.md`
- Token 优化分析: `TOKEN_OPTIMIZATION_ANALYSIS.md`

---

**创建日期**: 2026-01-22  
**最后更新**: 2026-01-22  
**版本**: 1.0
