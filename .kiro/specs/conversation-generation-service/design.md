# Design Document: Conversation Generation Service

## Overview

本设计文档描述基于 FastAPI 的对话生成服务框架。该框架采用分层架构，通过 Orchestrator 编排各子模块的调用流程，支持依赖注入、失败回退和 Token 计费。

核心设计原则：
- **模块化**: 每个子模块独立定义接口，支持独立开发和测试
- **可扩展**: 通过抽象基类和依赖注入，方便替换实现
- **可观测**: 完整的日志记录和计费追踪
- **高可用**: 多层失败回退策略

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                       │
├─────────────────────────────────────────────────────────────────┤
│                          API Layer                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              POST /api/v1/generate/reply                │    │
│  └─────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│                        Service Layer                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Orchestrator                          │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │    │
│  │  │ Context  │→ │  Scene   │→ │ Persona  │→ │  Reply   │ │    │
│  │  │ Builder  │  │ Analysis │  │Inference │  │Generator │ │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │    │
│  │                                               ↓          │    │
│  │                                         ┌──────────┐     │    │
│  │                                         │ Intimacy │     │    │
│  │                                         │  Check   │     │    │
│  │                                         └──────────┘     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              ↓                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ LLM Adapter  │  │   Billing    │  │ UserProfile  │           │
│  │  (已实现)     │  │   Service    │  │  (已实现)     │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
├─────────────────────────────────────────────────────────────────┤
│                      Persistence Layer                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  scene_analysis_log | persona_snapshot | llm_call_log    │   │
│  │  intimacy_check_log | generation_result                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. API Layer - GenerateReplyRouter

负责处理 HTTP 请求，验证参数，调用 Orchestrator。

```python
# 请求模型
class GenerateReplyRequest(BaseModel):
    user_id: str
    target_id: str
    conversation_id: str
    language: str = "en"  # Default to English (supports en/ar/pt/es/zh-CN)
    quality: Literal["cheap", "normal", "premium"] = "normal"
    force_regenerate: bool = False

# 响应模型
class GenerateReplyResponse(BaseModel):
    reply_text: str
    confidence: float
    intimacy_level_before: int
    intimacy_level_after: int
    model: str
    provider: str
    cost_usd: float
```

### 2. Orchestrator - 流程编排器

核心编排服务，协调各子模块的调用顺序。

```python
class Orchestrator:
    def __init__(
        self,
        context_builder: BaseContextBuilder,
        scene_analyzer: BaseSceneAnalyzer,
        persona_inferencer: BasePersonaInferencer,
        reply_generator: BaseReplyGenerator,
        intimacy_checker: BaseIntimacyChecker,
        billing_service: BillingService,
        config: OrchestratorConfig
    ): ...

    async def generate_reply(
        self, 
        request: GenerateReplyRequest
    ) -> GenerateReplyResponse: ...
```

### 3. 子模块抽象接口

#### 3.1 BaseContextBuilder

```python
class ContextBuilderInput(BaseModel):
    user_id: str
    target_id: str
    conversation_id: str
    history_dialog: list[Message]
    emotion_trend: EmotionSummary | None

class ContextResult(BaseModel):
    conversation_summary: str
    emotion_state: str
    current_intimacy_level: int
    risk_flags: list[str]

class BaseContextBuilder(ABC):
    @abstractmethod
    async def build_context(self, input: ContextBuilderInput) -> ContextResult: ...
```

#### 3.2 BaseSceneAnalyzer

```python
class SceneAnalysisInput(BaseModel):
    conversation_id: str
    history_dialog: list[Message]
    emotion_trend: EmotionSummary | None

class SceneAnalysisResult(BaseModel):
    scene: Literal["破冰", "推进", "冷却", "维持"]
    intimacy_level: int  # 1-5
    risk_flags: list[str]

class BaseSceneAnalyzer(ABC):
    @abstractmethod
    async def analyze_scene(self, input: SceneAnalysisInput) -> SceneAnalysisResult: ...
```

#### 3.3 BasePersonaInferencer

```python
class PersonaInferenceInput(BaseModel):
    user_id: str
    conversation_id: str
    scene: str
    history_dialog: list[Message]

class PersonaSnapshot(BaseModel):
    style: Literal["理性", "感性", "幽默", "克制"]
    pacing: Literal["slow", "normal", "fast"]
    risk_tolerance: Literal["low", "medium", "high"]
    confidence: float

class BasePersonaInferencer(ABC):
    @abstractmethod
    async def infer_persona(self, input: PersonaInferenceInput) -> PersonaSnapshot: ...
```

#### 3.4 BaseReplyGenerator

```python
class ReplyGenerationInput(BaseModel):
    prompt: str
    quality: Literal["cheap", "normal", "premium"]
    context: ContextResult
    scene: SceneAnalysisResult
    persona: PersonaSnapshot

class LLMResult(BaseModel):
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

class BaseReplyGenerator(ABC):
    @abstractmethod
    async def generate_reply(self, input: ReplyGenerationInput) -> LLMResult: ...
```

#### 3.5 BaseIntimacyChecker

```python
class IntimacyCheckInput(BaseModel):
    reply_text: str
    intimacy_level: int
    persona: PersonaSnapshot

class IntimacyCheckResult(BaseModel):
    passed: bool
    score: float
    reason: str | None

class BaseIntimacyChecker(ABC):
    @abstractmethod
    async def check(self, input: IntimacyCheckInput) -> IntimacyCheckResult: ...
```

### 4. BillingService - 计费服务

```python
class LLMCallRecord(BaseModel):
    user_id: str
    task_type: Literal["scene", "persona", "generation", "qc"]
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    created_at: datetime

class BillingService:
    async def record_call(self, record: LLMCallRecord) -> None: ...
    async def get_total_cost(self, user_id: str) -> float: ...
    async def check_quota(self, user_id: str) -> bool: ...
```

### 5. Mock 实现

为每个子模块提供 Mock 实现，返回默认值，方便开发和测试。

```python
class MockContextBuilder(BaseContextBuilder):
    async def build_context(self, input: ContextBuilderInput) -> ContextResult:
        return ContextResult(
            conversation_summary="Mock summary",
            emotion_state="neutral",
            current_intimacy_level=3,
            risk_flags=[]
        )

# 类似地为其他子模块提供 Mock 实现
```

### 6. 依赖注入容器

```python
class ServiceContainer:
    def __init__(self, config: AppConfig):
        self.config = config
        self._services: dict[str, Any] = {}
    
    def register(self, name: str, service: Any) -> None: ...
    def get(self, name: str) -> Any: ...
    
    def create_orchestrator(self) -> Orchestrator: ...
```

## Data Models

### 核心数据模型

```python
class Message(BaseModel):
    id: str
    speaker: Literal["user", "target"]
    content: str
    timestamp: datetime

class EmotionSummary(BaseModel):
    trend: Literal["positive", "negative", "neutral"]
    intensity: float  # 0-1
    recent_emotions: list[str]

class OrchestratorConfig(BaseModel):
    max_retries: int = 3
    timeout_seconds: float = 30.0
    cost_limit_usd: float = 0.1
    fallback_model: str = "gpt-3.5-turbo"
```

### 数据库模型 (SQLAlchemy)

```python
class SceneAnalysisLog(Base):
    __tablename__ = "scene_analysis_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str]
    scene: Mapped[str]
    intimacy_level: Mapped[int]
    risk_flags: Mapped[dict]  # JSON
    model: Mapped[str]
    provider: Mapped[str]
    created_at: Mapped[datetime]

class PersonaSnapshotModel(Base):
    __tablename__ = "persona_snapshot"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str]
    conversation_id: Mapped[str]
    style: Mapped[str]
    pacing: Mapped[str]
    risk_tolerance: Mapped[str]
    confidence: Mapped[float]
    created_at: Mapped[datetime]

class LLMCallLog(Base):
    __tablename__ = "llm_call_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str]
    task_type: Mapped[str]
    provider: Mapped[str]
    model: Mapped[str]
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    cost_usd: Mapped[float]
    latency_ms: Mapped[int]
    created_at: Mapped[datetime]

class IntimacyCheckLog(Base):
    __tablename__ = "intimacy_check_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str]
    reply_text: Mapped[str]
    passed: Mapped[bool]
    score: Mapped[float]
    reason: Mapped[str | None]
    model: Mapped[str]
    created_at: Mapped[datetime]

class GenerationResultModel(Base):
    __tablename__ = "generation_result"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str]
    reply_text: Mapped[str]
    intimacy_before: Mapped[int]
    intimacy_after: Mapped[int]
    model: Mapped[str]
    provider: Mapped[str]
    cost_usd: Mapped[float]
    created_at: Mapped[datetime]
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Request Validation Consistency

*For any* request with missing or invalid required fields (user_id, target_id, conversation_id), the API SHALL return a 400 status code with error details, and no downstream services SHALL be invoked.

**Validates: Requirements 1.2, 1.3**

### Property 2: Response Schema Completeness

*For any* successful generation request, the response SHALL contain all required fields (reply_text, confidence, intimacy_level_before, intimacy_level_after, model, provider, cost_usd) with valid values.

**Validates: Requirements 1.4**

### Property 3: Service Invocation Order

*For any* successful generation flow, the Orchestrator SHALL invoke services in the exact order: Context_Builder → Scene_Analysis → Persona_Inference → Reply_Generation → Intimacy_Check, and each service SHALL receive the output of its predecessor.

**Validates: Requirements 2.1, 2.2**

### Property 4: Retry Limit Enforcement

*For any* generation request where Intimacy_Check fails, the system SHALL retry at most max_retries times (default 3), and after exhausting retries SHALL return a fallback response or error.

**Validates: Requirements 2.3, 2.4, 4.2**

### Property 5: Timeout Fallback Model Selection

*For any* LLM call that times out, the Orchestrator SHALL retry with the configured fallback_model (lower-tier model).

**Validates: Requirements 4.1**

### Property 6: Cost Limit Enforcement

*For any* generation request, if the accumulated cost exceeds cost_limit_usd, the system SHALL force subsequent LLM calls to use "cheap" quality tier.

**Validates: Requirements 4.3**

### Property 7: Exception Handling Consistency

*For any* exception thrown by a sub-module, the Orchestrator SHALL log the error and return a user-friendly error response without exposing internal details.

**Validates: Requirements 4.4, 4.5**

### Property 8: Billing Record Completeness

*For any* LLM call made during generation, the Billing_Service SHALL record a complete entry with provider, model, input_tokens, output_tokens, cost_usd, and the total cost in the response SHALL equal the sum of all recorded costs.

**Validates: Requirements 5.1, 5.2**

### Property 9: Quota Enforcement

*For any* user whose accumulated cost exceeds their quota, the system SHALL reject new requests with a quota exceeded error before invoking any services.

**Validates: Requirements 5.4**

### Property 10: Data Persistence Integrity

*For any* completed generation flow, the system SHALL persist records to scene_analysis_log, persona_snapshot, llm_call_log, intimacy_check_log, and generation_result tables, and these records SHALL be retrievable by their respective IDs.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

## Error Handling

### Error Categories

| Error Type | HTTP Status | Response Format |
|------------|-------------|-----------------|
| Validation Error | 400 | `{"error": "validation_error", "details": [...]}` |
| Quota Exceeded | 402 | `{"error": "quota_exceeded", "message": "..."}` |
| Service Timeout | 504 | `{"error": "timeout", "message": "..."}` |
| Internal Error | 500 | `{"error": "internal_error", "message": "..."}` |
| Fallback Response | 200 | Normal response with `fallback: true` flag |

### Fallback Strategies

```python
class FallbackStrategy:
    @staticmethod
    def get_conservative_reply(context: ContextResult) -> str:
        """返回保守的模板回复"""
        templates = {
            "破冰": "我觉得我们可以慢慢聊，不着急。",
            "推进": "这个话题挺有意思的，你怎么看？",
            "冷却": "好的，我理解。",
            "维持": "嗯嗯，是这样的。"
        }
        return templates.get(context.scene, "好的，我明白了。")
```

### Retry Configuration

```python
class RetryConfig(BaseModel):
    max_retries: int = 3
    retry_delay_seconds: float = 0.5
    exponential_backoff: bool = True
    fallback_on_exhaustion: bool = True
```

## Testing Strategy

### Unit Tests

单元测试覆盖以下场景：
- API 请求参数验证（有效/无效输入）
- Orchestrator 流程控制逻辑
- 各子模块 Mock 实现的默认行为
- BillingService 成本计算和记录
- 配置加载和验证

### Property-Based Tests

使用 `hypothesis` 库进行属性测试，每个属性测试运行至少 100 次迭代。

测试框架配置：
```python
from hypothesis import given, strategies as st, settings

@settings(max_examples=100)
```

属性测试覆盖：
- Property 1: 生成各种无效请求，验证返回 400
- Property 2: 生成有效请求，验证响应包含所有必需字段
- Property 3: 使用 Mock 追踪调用顺序
- Property 4: 模拟 Intimacy_Check 失败，验证重试次数
- Property 8: 验证计费记录完整性和成本汇总

### Integration Tests

集成测试验证：
- 完整的生成流程（使用 Mock 子模块）
- 数据库持久化
- 失败回退场景

### Test File Structure

```
tests/
├── unit/
│   ├── test_api_validation.py
│   ├── test_orchestrator.py
│   ├── test_billing_service.py
│   └── test_config.py
├── property/
│   ├── test_request_validation_property.py
│   ├── test_response_schema_property.py
│   ├── test_retry_property.py
│   └── test_billing_property.py
└── integration/
    ├── test_generation_flow.py
    └── test_persistence.py
```
