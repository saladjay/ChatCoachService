"""Core business models for the conversation generation service.

This module defines Pydantic models for:
- Message: Individual conversation messages
- EmotionSummary: Emotion trend analysis
- PersonaSnapshot: User persona inference results
- Context and analysis related models
"""

from datetime import datetime
from typing import Literal, Union, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Represents a single message in a conversation."""

    id: str
    speaker: Union[Literal["user"], str]
    content: str
    timestamp: Optional[datetime]


class EmotionSummary(BaseModel):
    """Summary of emotion trends in a conversation."""

    trend: Literal["positive", "negative", "neutral"]
    intensity: float = Field(ge=0.0, le=1.0, description="Emotion intensity from 0 to 1")
    recent_emotions: list[str] = Field(default_factory=list)


class PersonaSnapshot(BaseModel):
    """Snapshot of inferred user persona characteristics."""

    # style: str
    pacing: Literal["slow", "normal", "fast"]
    risk_tolerance: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from 0 to 1")
    prompt: str


class ContextBuilderInput(BaseModel):
    """Input for the context builder service."""
    user_id: str
    target_id: str
    conversation_id: str
    history_dialog: list[Message] = Field(default_factory=list)
    emotion_trend: EmotionSummary | None = None


class ContextResult(BaseModel):
    """Result from the context builder service."""

    conversation_summary: str # 对话摘要/总结
    emotion_state: str # 情绪状态
    current_intimacy_level: int = Field(ge=0, le=100)  # 当前亲密度等级（范围0-100）
    risk_flags: list[str] = Field(default_factory=list) # 风险标识/风险标记列表（默认空列表）
    conversation: list[Message] = Field(default=[])
    history_conversation: str = ""


class SceneAnalysisInput(BaseModel):
    """Input for the scene analysis service."""

    conversation_id: str
    history_dialog: list[Message] = Field(default_factory=list)
    emotion_trend: EmotionSummary | None = None
    history_topic_summary: str = ""  # 历史对话话题总结
    current_conversation_summary: str = ""  # 当前对话总结
    current_conversation: list[Message] = Field(default_factory=list)  # 当前对话
    intimacy_value: int = Field(default=50, ge=0, le=100)  # 用户设置的亲密度
    current_intimacy_level: int = Field(default=50, ge=0, le=100)  # 当前分析的亲密度


class SceneAnalysisResult(BaseModel):
    """Result from the scene analysis service."""

    relationship_state: Literal["破冰", "推进", "冷却", "维持",
                                "ignition","propulsion","ventilation","equilibrium"]
    scenario: str  # 推荐情景（从 recommended_scenario 获取）
    intimacy_level: int = Field(ge=0, le=100)  # 用户设置的亲密度
    risk_flags: list[str] = Field(default_factory=list)  # 基于亲密度差异的风险标记
    current_scenario: str = ""  # 当前情景（安全/低风险策略|平衡/中风险策略|高风险/高回报策略|关系修复策略|禁止的策略）
    recommended_scenario: str = ""  # 推荐情景
    recommended_strategies: list[str] = Field(default_factory=list)  # 推荐的对话策略（3个策略代码）


class PersonaInferenceInput(BaseModel):
    """Input for the persona inference service."""

    user_id: str
    conversation_id: str
    scene: str
    history_dialog: list[Message] = Field(default_factory=list)
    persona: str = ""
    intimacy: int = Field(default=50, ge=0, le=100)
    relationship_state: Literal["破冰", "推进", "冷却", "维持",
                                "ignition","propulsion","ventilation","equilibrium"]


class ReplyGenerationInput(BaseModel):
    """Input for the reply generation service."""

    user_id: str
    prompt: str
    quality: Literal["cheap", "normal", "premium"] = "normal"
    context: ContextResult
    scene: SceneAnalysisResult
    persona: PersonaSnapshot
    reply_sentence: str = ""  # 客户选择由你回复的一句话（默认为空）
    language: str = "en"  # 生成回复的语言（默认英语，支持 en/ar/pt/es 等）


class LLMResult(BaseModel):
    """Result from an LLM call."""

    text: str
    provider: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)


class IntimacyCheckInput(BaseModel):
    """Input for the intimacy check service."""

    reply_text: str
    intimacy_level: int = Field(ge=0, le=100)
    persona: PersonaSnapshot
    scene: SceneAnalysisResult
    context: ContextResult
    


class IntimacyCheckResult(BaseModel):
    """Result from the intimacy check service."""

    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    scores: list[float] = Field(default_factory=list)
    reason: str | None = None


class LLMCallRecord(BaseModel):
    """Record of an LLM call for billing purposes."""

    user_id: str
    task_type: Literal["scene", "persona", "generation", "qc"]
    provider: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    latency_ms: int = Field(ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OrchestratorConfig(BaseModel):
    """Configuration for the orchestrator service."""

    max_retries: int = Field(default=3, ge=1)
    timeout_seconds: float = Field(default=30.0, gt=0)
    cost_limit_usd: float = Field(default=0.1, gt=0)
    fallback_model: str = "gpt-3.5-turbo"
