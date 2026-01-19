"""UserProfile Service - 集成 core/user_profile 的用户画像服务。

本模块集成 over-seas-user-profile-service，提供：
- 三层画像管理（显式标签、行为偏好、会话状态）
- 场景分析与策略推荐
- LLM 友好的画像序列化
- 上下文敏感的画像视图

Requirements: 3.2
"""

import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from app.models.schemas import (
    Message,
    PersonaInferenceInput,
    PersonaSnapshot,
)
from app.services.base import BasePersonaInferencer
from app.services.llm_adapter import BaseLLMAdapter, LLMCall
from app.services.prompt import *
# 添加 user_profile 到 path
USER_PROFILE_PATH = Path(__file__).parent.parent.parent / "core" / "user_profile" / "src"
if str(USER_PROFILE_PATH) not in sys.path:
    sys.path.insert(0, str(USER_PROFILE_PATH))

from user_profile import (
    # 核心管理器
    ProfileManager,
    
    # 数据模型
    UserProfile as CoreUserProfile,
    ExplicitTags,
    BehavioralTraits,
    BehavioralPreference,
    SessionState,
    BehaviorSignals,
    
    # 场景分析
    ScenarioAnalysis,
    ScenarioRiskLevel,
    SafeStrategy,
    BalancedStrategy,
    RiskyStrategy,
    RecoveryStrategy,
    
    # 上下文分析
    ContextAnalyzer,
    ConversationContext,
    ConversationMessage,
    ContextualOverlay,
    
    # 序列化
    OutputFormat,
    SerializationConfig,
    
    # 存储
    InMemoryProfileStore,
)

from user_profile.preference_learner import (
    PreferenceLearner,
    LearnedPreference,
    ResponseClusterFeatures,
    UserInputPreference,
    PreferenceSource,
)


# ============== 风格映射 ==============

# 将 core/user_profile 的风格映射到 chatcoach 的风格
STYLE_MAPPING = {
    "理性": "理性",
    "感性": "感性",
    "幽默": "幽默",
    "克制": "克制",
}

# 将场景风险等级映射到节奏
RISK_TO_PACING = {
    ScenarioRiskLevel.SAFE: "slow",
    ScenarioRiskLevel.BALANCED: "normal",
    ScenarioRiskLevel.RISKY: "fast",
    ScenarioRiskLevel.RECOVERY: "slow",
    ScenarioRiskLevel.NEGATIVE: "slow",
}

# 将场景风险等级映射到风险容忍度
RISK_TO_TOLERANCE = {
    ScenarioRiskLevel.SAFE: "low",
    ScenarioRiskLevel.BALANCED: "medium",
    ScenarioRiskLevel.RISKY: "high",
    ScenarioRiskLevel.RECOVERY: "low",
    ScenarioRiskLevel.NEGATIVE: "low",
}


# ============== 兼容层：简化的 UserProfile ==============

class UserProfile:
    """简化的用户画像，用于兼容现有代码。
    
    内部使用 core/user_profile 的完整画像。
    """
    
    def __init__(
        self,
        user_id: str,
        style: Literal["理性", "感性", "幽默", "克制"] = "理性",
        pacing: Literal["slow", "normal", "fast"] = "normal",
        risk_tolerance: Literal["low", "medium", "high"] = "medium",
        adoption_rate: float = 0.5,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        # 扩展字段
        core_profile: Optional[CoreUserProfile] = None,
    ):
        self.user_id = user_id
        self.style = style
        self.pacing = pacing
        self.risk_tolerance = risk_tolerance
        self.adoption_rate = adoption_rate
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        self._core_profile = core_profile
    
    @property
    def core_profile(self) -> Optional[CoreUserProfile]:
        """获取底层的完整画像。"""
        return self._core_profile
    
    @classmethod
    def from_core_profile(cls, core_profile: CoreUserProfile) -> "UserProfile":
        """从 core/user_profile 的画像创建简化画像。"""
        # 从显式标签提取风格
        style = "理性"
        if core_profile.explicit.style:
            first_style = core_profile.explicit.style[0]
            style = STYLE_MAPPING.get(first_style, "理性")
        
        # 从场景分析提取节奏和风险容忍度
        pacing = "normal"
        risk_tolerance = "medium"
        
        if core_profile.session_state and core_profile.session_state.scenario:
            scenario = core_profile.session_state.scenario
            pacing = RISK_TO_PACING.get(scenario.risk_level, "normal")
            risk_tolerance = RISK_TO_TOLERANCE.get(scenario.risk_level, "medium")
        
        return cls(
            user_id=core_profile.user_id,
            style=style,
            pacing=pacing,
            risk_tolerance=risk_tolerance,
            created_at=core_profile.created_at,
            updated_at=core_profile.updated_at,
            core_profile=core_profile,
        )


# ============== 服务接口 ==============

class BaseUserProfileService(ABC):
    """用户画像服务抽象基类。"""
    
    @abstractmethod
    async def get_profile(self, user_id: str) -> UserProfile | None:
        """获取用户画像。"""
        ...
    
    @abstractmethod
    async def update_profile(self, profile: UserProfile) -> None:
        """更新用户画像。"""
        ...
    
    @abstractmethod
    async def create_profile(self, user_id: str) -> UserProfile:
        """创建用户画像。"""
        ...
    
    @abstractmethod
    async def learn_preferences_from_conversation(
        self,
        user_id: str,
        messages: list[Message],
    ) -> list[LearnedPreference]:
        """从对话上下文学习用户偏好。"""
        ...


class UserProfileService(BaseUserProfileService):
    """用户画像服务实现，集成 core/user_profile。
    
    提供完整的用户画像管理能力：
    - 三层画像（显式标签、行为偏好、会话状态）
    - 场景分析与策略推荐
    - 上下文敏感的画像视图
    - LLM 友好的序列化输出
    - 从对话上下文学习用户偏好
    
    Requirements: 3.2
    """
    
    # LLM 分析对话偏好的 Prompt 模板
    
    
    def __init__(self, llm_adapter: BaseLLMAdapter | None = None):
        """初始化用户画像服务。
        
        Args:
            llm_adapter: LLM 适配器，用于分析对话偏好。如果为 None，则禁用 LLM 分析功能。
        """
        self._store = InMemoryProfileStore()
        self._manager = ProfileManager(store=self._store)
        self._context_analyzer = ContextAnalyzer()
        self._preference_learner = PreferenceLearner()
        self._llm_adapter = llm_adapter
    
    @property
    def manager(self) -> ProfileManager:
        """获取底层的 ProfileManager。"""
        return self._manager
    
    @property
    def context_analyzer(self) -> ContextAnalyzer:
        """获取上下文分析器。"""
        return self._context_analyzer
    
    # ==================== 基础操作 ====================
    
    async def get_profile(self, user_id: str) -> UserProfile | None:
        """获取用户画像。"""
        core_profile = self._manager.get_profile(user_id)
        if core_profile is None:
            return None
        return UserProfile.from_core_profile(core_profile)
    
    async def update_profile(self, profile: UserProfile) -> None:
        """更新用户画像。"""
        core_profile = self._manager.get_or_create_profile(profile.user_id)
        
        # 更新显式标签
        if profile.style:
            core_profile.explicit.style = [profile.style]
        
        core_profile.explicit.updated_at = datetime.now()
        self._manager.save_profile(core_profile)
    
    async def create_profile(self, user_id: str) -> UserProfile:
        """创建用户画像。"""
        core_profile = self._manager.get_or_create_profile(user_id)
        return UserProfile.from_core_profile(core_profile)
    
    async def get_or_create_profile(self, user_id: str) -> UserProfile:
        """获取或创建用户画像。"""
        profile = await self.get_profile(user_id)
        if profile is None:
            profile = await self.create_profile(user_id)
        return profile
    
    # ==================== 显式标签管理 ====================
    
    async def set_explicit_tags(
        self,
        user_id: str,
        role: list[str] | None = None,
        style: list[str] | None = None,
        forbidden: list[str] | None = None,
        intimacy: float | None = None,
    ) -> UserProfile:
        """设置用户的显式标签。
        
        Args:
            user_id: 用户ID
            role: 角色人设标签
            style: 回复风格标签
            forbidden: 禁止事项标签
            intimacy: 亲密度 (0-100)
        
        Returns:
            更新后的用户画像
        """
        core_profile = self._manager.quick_setup_profile(
            user_id=user_id,
            role=role,
            style=style,
            forbidden=forbidden,
            intimacy=intimacy or 50.0,
        )
        return UserProfile.from_core_profile(core_profile)
    
    async def add_tag(
        self,
        user_id: str,
        category: str,
        name: str,
        value: Any,
    ) -> None:
        """添加显式标签。"""
        self._manager.add_tag(user_id, category, name, value)
    
    async def get_tags(self, user_id: str, category: str | None = None) -> list[dict]:
        """获取用户标签。"""
        tags = self._manager.list_tags(user_id, category)
        return [
            {
                "category": tag.category,
                "name": tag.name,
                "value": tag.value,
            }
            for tag in tags
        ]
    
    # ==================== 场景分析 ====================
    
    async def analyze_scenario(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[Message],
        use_llm: bool = True,
        provider=None,
        model=None
    ) -> UserProfile:
        """分析对话场景并更新用户画像。
        
        使用 LLM 分析对话内容，自动推断场景风险等级、关系阶段、
        情绪基调、推荐策略和需要回避的模式。
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            messages: 对话历史
            use_llm: 是否使用 LLM 分析（默认 True）
        
        Returns:
            更新后的用户画像
        
        Raises:
            ValueError: 如果 use_llm=True 但 LLM adapter 未配置
        """
        if use_llm:
            if self._llm_adapter is None:
                raise ValueError("LLM adapter not configured, cannot analyze scenario with LLM")
            
            # 使用 LLM 分析场景
            analysis = await self._analyze_scenario_with_llm(user_id, messages, provider=provider, model=model)
            
            risk_level = self._parse_risk_level(analysis.get("risk_level", "safe"))
            recommended_strategies = analysis.get("recommended_strategies", [])
            avoid_patterns = analysis.get("avoid_patterns", [])
            relationship_stage = analysis.get("relationship_stage", "stranger")
            emotional_tone = analysis.get("emotional_tone", "neutral")
        else:
            # 使用默认值
            risk_level = ScenarioRiskLevel.SAFE
            recommended_strategies = []
            avoid_patterns = []
            relationship_stage = "stranger"
            emotional_tone = "neutral"
        
        core_profile = self._manager.get_or_create_profile(user_id)
        
        # 创建场景分析结果
        scenario = ScenarioAnalysis(
            risk_level=risk_level,
            recommended_strategies=recommended_strategies,
            avoid_patterns=avoid_patterns,
            relationship_stage=relationship_stage,
            emotional_tone=emotional_tone,
        )
        
        # 创建会话状态
        session_state = SessionState(
            conversation_id=conversation_id,
            scenario=scenario,
        )
        
        # 更新画像
        core_profile = self._manager.update_session_state(user_id, session_state)
        
        return UserProfile.from_core_profile(core_profile)
    
    async def _analyze_scenario_with_llm(
        self,
        user_id: str,
        messages: list[Message],
        provider=None,
        model=None
    ) -> dict:
        """使用 LLM 分析对话场景。
        
        Args:
            user_id: 用户ID
            messages: 对话消息列表
        
        Returns:
            分析结果字典
        """
        if not messages:
            return {}
        
        # 构建对话文本
        conversation_text = self._format_conversation(messages)
        
        # 调用 LLM 分析场景
        prompt = SCENARIO_ANALYSIS_PROMPT.format(conversation=conversation_text)
        llm_call = LLMCall(
            task_type="persona",
            prompt=prompt,
            quality="normal",
            user_id=user_id,
            provider=provider,
            model=model
        )
        
        result = await self._llm_adapter.call(llm_call)
        print('result:', result)
        # 解析 LLM 返回的 JSON
        return self._parse_scenario_response(result.text)
    
    def _parse_scenario_response(self, response_text: str) -> dict:
        """解析 LLM 返回的场景分析结果。"""
        import json
        
        text = response_text.strip()
        
        # 处理 markdown 代码块
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()
        
        # 提取 JSON 对象
        if "{" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "risk_level": "safe",
                "relationship_stage": "stranger",
                "emotional_tone": "neutral",
                "recommended_strategies": [],
                "avoid_patterns": [],
                "confidence": 0.5,
                "analysis": "Failed to parse LLM response",
            }
    
    def _parse_risk_level(self, risk_level_str: str) -> ScenarioRiskLevel:
        """将字符串转换为 ScenarioRiskLevel 枚举。"""
        risk_level_map = {
            "safe": ScenarioRiskLevel.SAFE,
            "balanced": ScenarioRiskLevel.BALANCED,
            "risky": ScenarioRiskLevel.RISKY,
            "recovery": ScenarioRiskLevel.RECOVERY,
        }
        return risk_level_map.get(risk_level_str.lower(), ScenarioRiskLevel.SAFE)
    
    async def analyze_scenario_manual(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[Message],
        risk_level: ScenarioRiskLevel = ScenarioRiskLevel.SAFE,
        recommended_strategies: list[str] | None = None,
        avoid_patterns: list[str] | None = None,
        relationship_stage: str = "stranger",
        emotional_tone: str = "neutral",
    ) -> UserProfile:
        """手动设置场景分析结果（不使用 LLM）。
        
        当你已经有场景分析结果时，可以直接使用此方法更新画像。
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            messages: 对话历史
            risk_level: 场景风险等级
            recommended_strategies: 推荐策略列表
            avoid_patterns: 需要回避的模式
            relationship_stage: 关系阶段
            emotional_tone: 情绪基调
        
        Returns:
            更新后的用户画像
        """
        core_profile = self._manager.get_or_create_profile(user_id)
        
        # 创建场景分析结果
        scenario = ScenarioAnalysis(
            risk_level=risk_level,
            recommended_strategies=recommended_strategies or [],
            avoid_patterns=avoid_patterns or [],
            relationship_stage=relationship_stage,
            emotional_tone=emotional_tone,
        )
        
        # 创建会话状态
        session_state = SessionState(
            conversation_id=conversation_id,
            scenario=scenario,
        )
        
        # 更新画像
        core_profile = self._manager.update_session_state(user_id, session_state)
        
        return UserProfile.from_core_profile(core_profile)
    
    async def get_recommended_strategies(self, user_id: str) -> list[str]:
        """获取当前推荐的策略列表。"""
        core_profile = self._manager.get_profile(user_id)
        if core_profile is None:
            return []
        
        if core_profile.session_state:
            return core_profile.session_state.get_recommended_strategies()
        return []
    
    async def get_avoid_patterns(self, user_id: str) -> list[str]:
        """获取需要回避的模式列表。"""
        core_profile = self._manager.get_profile(user_id)
        if core_profile is None:
            return []
        
        if core_profile.session_state:
            return core_profile.session_state.get_avoid_patterns()
        return []
    
    # ==================== 上下文分析 ====================
    
    async def analyze_context(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[Message],
    ) -> ContextualOverlay:
        """分析对话上下文。
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            messages: 对话历史
        
        Returns:
            上下文覆盖层
        """
        # 转换消息格式
        print(type(messages[0]))
        # print(ConversationMessage())
        conv_messages = [
            ConversationMessage(
                role=msg.speaker,
                content=msg.content,
                # timestamp=msg.timestamp,
                # metadata={}
            )
            for msg in messages
        ]
        
        # 创建对话上下文
        context = ConversationContext(
            conversation_id=conversation_id,
            messages=conv_messages,
        )
        
        # 获取用户画像
        core_profile = self._manager.get_profile(user_id)
        
        # 分析上下文
        overlay = self._context_analyzer.analyze_context(context, core_profile)
        
        return overlay
    
    # ==================== 行为信号更新 ====================
    
    async def update_from_behavior(
        self,
        user_id: str,
        asked_for_examples: bool = False,
        asked_why: bool = False,
        rejected_answer: bool = False,
        selected_response_index: int | None = None,
        message_length: str = "medium",
    ) -> UserProfile:
        """根据行为信号更新用户画像。
        
        Args:
            user_id: 用户ID
            asked_for_examples: 是否要求示例
            asked_why: 是否追问原因
            rejected_answer: 是否拒绝回答
            selected_response_index: 选择的回复索引
            message_length: 消息长度 (short/medium/long)
        
        Returns:
            更新后的用户画像
        """
        signals = BehaviorSignals(
            asked_for_examples=asked_for_examples,
            asked_why=asked_why,
            rejected_answer=rejected_answer,
            selected_response_index=selected_response_index,
            message_length=message_length,
        )
        
        core_profile = self._manager.update_from_signals(user_id, signals)
        return UserProfile.from_core_profile(core_profile)
    
    # ==================== 对话偏好学习 ====================
    
    async def learn_preferences_from_conversation(
        self,
        user_id: str,
        messages: list[Message],
        provider='dashscope',
        model='qwen-flash',
    ) -> list[LearnedPreference]:
        """从对话上下文学习用户偏好。
        
        使用 LLM 分析对话内容，提取用户的沟通偏好特征，
        然后通过 PreferenceLearner 将其转换为结构化的偏好数据。
        
        Args:
            user_id: 用户ID
            messages: 对话消息列表
        
        Returns:
            学习到的偏好列表
        
        Raises:
            ValueError: 如果 LLM adapter 未配置
        """
        print('learn_preferences_from_conversation start')
        if self._llm_adapter is None:
            raise ValueError("LLM adapter not configured, cannot analyze conversation preferences")
        print('message:', messages)
        if not messages:
            return []
        
        # 构建对话文本
        conversation_text = self._format_conversation(messages)
        print('conversation_text:', conversation_text)
        # 调用 LLM 分析对话偏好
        prompt = PREFERENCE_ANALYSIS_PROMPT.format(conversation=conversation_text)
        llm_call = LLMCall(
            task_type="persona",
            prompt=prompt,
            quality="normal",
            user_id=user_id,
            provider=provider,
            model=model
        )
        
        result = await self._llm_adapter.call(llm_call)
        
        # 解析 LLM 返回的 JSON
        cluster_features = self._parse_preference_response(result.text, len(messages))
        
        # 使用 PreferenceLearner 从聚类特征学习偏好
        learned_preferences = self._preference_learner.learn_from_response_clusters(
            user_id=user_id,
            cluster_features=cluster_features,
        )
        
        # 更新用户偏好（与现有偏好合并）
        self._preference_learner.update_user_preferences(user_id, learned_preferences)
        
        return learned_preferences
    
    def _format_conversation(self, messages: list[Message]) -> str:
        """将消息列表格式化为对话文本。"""
        lines = []
        for msg in messages:
            speaker = "用户" if msg.speaker == "user" else "助手"
            lines.append(f"{speaker}: {msg.content}")
        return "\n".join(lines)
    
    def _parse_preference_response(
        self,
        response_text: str,
        sample_count: int,
    ) -> ResponseClusterFeatures:
        """解析 LLM 返回的偏好分析结果。
        
        Args:
            response_text: LLM 返回的 JSON 文本
            sample_count: 分析的消息数量
        
        Returns:
            ResponseClusterFeatures 对象
        """
        import json
        
        try:
            # 尝试解析 JSON
            data = json.loads(response_text.strip())
            features = data.get("features", {})
            description = data.get("description", None)
            
            # 确保所有特征值在 0-1 范围内
            validated_features = {}
            for key, value in features.items():
                if isinstance(value, (int, float)):
                    validated_features[key] = max(0.0, min(1.0, float(value)))
            
            return ResponseClusterFeatures(
                cluster_id=f"conv_analysis_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                sample_count=sample_count,
                features=validated_features,
                description=description,
            )
        except json.JSONDecodeError:
            # 如果解析失败，返回空特征
            return ResponseClusterFeatures(
                cluster_id=f"conv_analysis_fallback_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                sample_count=sample_count,
                features={},
                description="Failed to parse LLM response",
            )
    
    async def get_learned_preferences(self, user_id: str) -> list[LearnedPreference]:
        """获取用户学习到的偏好列表。
        
        Args:
            user_id: 用户ID
        
        Returns:
            学习到的偏好列表
        """
        return self._preference_learner.get_user_preferences(user_id)
    
    async def add_user_preference(
        self,
        user_id: str,
        key: str,
        value: float,
        description: str | None = None,
    ) -> list[LearnedPreference]:
        """添加用户直接输入的偏好。
        
        用户直接输入的偏好具有最高置信度。
        
        Args:
            user_id: 用户ID
            key: 偏好键
            value: 偏好值 (0.0-1.0)
            description: 用户描述
        
        Returns:
            更新后的偏好列表
        """
        user_input = UserInputPreference(
            key=key,
            value=value,
            description=description,
        )
        
        learned = self._preference_learner.learn_from_user_input(
            user_id=user_id,
            preferences=[user_input],
        )
        
        return self._preference_learner.update_user_preferences(user_id, learned)
    
    # ==================== 序列化输出 ====================
    
    async def serialize_to_prompt(
        self,
        user_id: str,
        max_tokens: int = 500,
        language: str = "zh",
    ) -> str | None:
        """序列化画像为 Prompt 格式。"""
        return self._manager.serialize_to_prompt(user_id, max_tokens, language)
    
    async def serialize_to_tool(
        self,
        user_id: str,
        include_confidence: bool = False,
    ) -> dict | None:
        """序列化画像为 Tool 格式（用于 Function Calling）。"""
        return self._manager.serialize_to_tool(user_id, include_confidence)
    
    async def get_profile_for_llm(self, user_id: str) -> dict | None:
        """获取 LLM 友好的画像表示。"""
        core_profile = self._manager.get_profile(user_id)
        if core_profile is None:
            return None
        return core_profile.to_prompt_dict()


# ============== Persona Inferencer ==============

class UserProfilePersonaInferencer(BasePersonaInferencer):
    """基于 UserProfile 服务的 Persona 推理器。
    
    将 UserProfile 服务集成到 Orchestrator 流程中。
    
    Requirements: 3.2
    """
    
    def __init__(self, user_profile_service: UserProfileService):
        """初始化。
        
        Args:
            user_profile_service: 用户画像服务实例
        """
        self.user_profile_service = user_profile_service
    
    async def infer_persona(self, input: PersonaInferenceInput) -> PersonaSnapshot:
        """从对话数据推断用户画像。
        
        Args:
            input: 推理输入，包含 user_id、conversation_id、scene、history_dialog
        
        Returns:
            PersonaSnapshot 包含 style、pacing、risk_tolerance、confidence、prompt
        """
        # 获取或创建用户画像
        profile = await self.user_profile_service.get_or_create_profile(input.user_id)
        
        # 如果有对话历史，进行上下文分析
        if input.history_dialog:
            overlay = await self.user_profile_service.analyze_context(
                user_id=input.user_id,
                conversation_id=input.conversation_id,
                messages=input.history_dialog,
            )
            
            # 根据上下文调整画像
            # 这里可以根据 overlay 的分析结果进一步调整
        
        # 计算置信度
        confidence = self._calculate_confidence(input, profile)
        
        # 生成 prompt 字符串
        prompt = await self.user_profile_service.serialize_to_prompt(
            user_id=input.user_id,
            max_tokens=500,
            language="zh"
        )
        
        # 如果 prompt 为 None，使用默认值
        if prompt is None:
            prompt = f"用户画像：风格={profile.style}，节奏={profile.pacing}，风险容忍度={profile.risk_tolerance}"
        
        return PersonaSnapshot(
            style=profile.style,
            pacing=profile.pacing,
            risk_tolerance=profile.risk_tolerance,
            confidence=confidence,
            prompt=prompt,
        )
    
    def _calculate_confidence(
        self,
        input: PersonaInferenceInput,
        profile: UserProfile,
    ) -> float:
        """计算置信度。"""
        base_confidence = 0.7
        
        # 根据对话历史长度调整
        history_bonus = min(len(input.history_dialog) * 0.02, 0.2)
        
        # 根据场景调整
        scene_adjustments = {
            "破冰": -0.1,
            "推进": 0.0,
            "冷却": -0.05,
            "维持": 0.1,
        }
        scene_adjustment = scene_adjustments.get(input.scene, 0.0)
        
        # 如果有完整的 core_profile，置信度更高
        if profile.core_profile is not None:
            base_confidence += 0.05
        
        confidence = base_confidence + history_bonus + scene_adjustment
        return max(0.0, min(1.0, confidence))
