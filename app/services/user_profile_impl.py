"""UserProfile Service - 集成 core/user_profile 的用户画像服务。

本模块集成 over-seas-user-profile-service，提供：
- 三层画像管理（显式标签、行为偏好、会话状态）
- 场景分析与策略推荐
- LLM 友好的画像序列化
- 上下文敏感的画像视图

Requirements: 3.2

主要接口速览（UserProfileService）：

- get_profile(user_id) -> UserProfile | None
- create_profile(user_id) -> UserProfile
- update_profile(profile) -> None
- get_or_create_profile(user_id) -> UserProfile

- set_explicit_tags(user_id, role=None, style=None, forbidden=None, intimacy=None) -> UserProfile
- add_tag(user_id, category, name, value) -> None
- get_tags(user_id, category=None) -> list[dict]

- analyze_scenario(user_id, conversation_id, messages=None, provider=None, model=None) -> UserProfile
- analyze_scenario_manual(user_id, conversation_id, risk_level, intimacy=None) -> UserProfile
- get_recommended_strategies(user_id) -> list[str]
- get_avoid_patterns(user_id) -> list[str]

- analyze_context(user_id, conversation_id, messages) -> ContextualOverlay

- update_from_behavior(user_id, asked_for_examples=False, asked_why=False, rejected_answer=False,
  selected_response_index=None, message_length="medium", response_time_seconds=None, custom_signals=None) -> UserProfile

- learn_preferences_from_conversation(user_id, messages) -> list[LearnedPreference]
- learn_new_traits(user_id, messages=None, selected_sentences=None, provider=None, model=None,
  store=True, map_to_standard=True) -> dict[str, Any]
- map_traits_to_standard(user_id, traits) -> list[dict[str, Any]]

- serialize_to_prompt(user_id, max_tokens=500, language="zh") -> str
- serialize_to_tool(user_id, include_confidence=False) -> dict
- get_profile_for_llm(user_id) -> dict | None
"""

import sys
import importlib
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional
import json
import os

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

importlib.invalidate_caches()
_existing_user_profile = sys.modules.get("user_profile")
if _existing_user_profile is not None:
    _existing_file = getattr(_existing_user_profile, "__file__", None)
    try:
        _expected_prefix = str(USER_PROFILE_PATH.resolve())
        if _existing_file is None:
            del sys.modules["user_profile"]
        else:
            _existing_file = str(Path(_existing_file).resolve())
            if not _existing_file.casefold().startswith(_expected_prefix.casefold()):
                del sys.modules["user_profile"]
    except Exception:
        pass

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
    STANDARD_TRAITS as CORE_STANDARD_TRAITS,
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

    @abstractmethod
    async def learn_new_traits(
        self,
        user_id: str,
        messages: list[Message] | None = None,
        selected_sentences: list[str] | None = None,
        provider: str | None = None,
        model: str | None = None,
        store: bool = True,
        map_to_standard: bool = True,
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    async def get_trait_vector(self, user_id: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    async def update_trait_vector_from_mappings(
        self,
        user_id: str,
        mappings: list[dict[str, Any]],
        *,
        source: str = "trait_mapping",
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    async def set_trait_frozen(
        self,
        user_id: str,
        trait_name: str,
        frozen: bool = True,
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    async def rollback_profile(self, user_id: str, steps: int = 1) -> dict[str, Any] | None:
        ...

    @abstractmethod
    async def rollback_profile_to_version(
        self,
        user_id: str,
        target_version: int,
    ) -> dict[str, Any] | None:
        ...

    @abstractmethod
    async def get_version_history(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def list_new_trait_pool(
        self,
        user_id: str,
        *,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def review_new_trait_candidate(
        self,
        user_id: str,
        trait_name: str,
        action: str,
        *,
        merged_into: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any] | None:
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
        trait_rules = self._load_trait_rules_from_yaml()
        self._store = InMemoryProfileStore()
        self._manager = ProfileManager(store=self._store, trait_rules=trait_rules)
        self._context_analyzer = ContextAnalyzer()
        self._preference_learner = PreferenceLearner()
        self._llm_adapter = llm_adapter

    def _load_trait_rules_from_yaml(self) -> dict[str, Any] | None:
        try:
            import yaml
        except Exception:
            return None

        env_path = os.environ.get("PROFILE_RULES_CONFIG_PATH")
        repo_root = Path(__file__).resolve().parents[2]
        candidates: list[Path] = []
        if env_path:
            candidates.append(Path(env_path))
        candidates.append(repo_root / "profile_rules.yaml")
        candidates.append(repo_root / "core" / "llm_adapter" / "config.yaml")

        path = next((p for p in candidates if p.exists() and p.is_file()), None)
        if path is None:
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
        except Exception:
            return None

        if not isinstance(raw, dict):
            return None

        profile_section = raw.get("profile")
        if isinstance(profile_section, dict):
            trait_rules = profile_section.get("trait_rules")
            if isinstance(trait_rules, dict):
                return trait_rules

        trait_rules = raw.get("trait_rules")
        if isinstance(trait_rules, dict):
            return trait_rules

        return None
    
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

    def _trait_vector_to_dict(self, trait_vector: Any) -> dict[str, Any]:
        if trait_vector is None:
            return {
                "schema_version": None,
                "updated_at": None,
                "traits": {},
            }

        traits: dict[str, Any] = {}
        raw_traits = getattr(trait_vector, "traits", None)
        if isinstance(raw_traits, dict):
            for name, state in raw_traits.items():
                if not isinstance(name, str):
                    continue
                traits[name] = {
                    "value": getattr(state, "value", None),
                    "evidence_count": getattr(state, "evidence_count", None),
                    "confidence": getattr(state, "confidence", None),
                    "last_direction": getattr(state, "last_direction", None),
                    "direction_streak": getattr(state, "direction_streak", None),
                    "frozen": getattr(state, "frozen", None),
                    "evidence": list(getattr(state, "evidence", []) or []),
                    "last_updated_at": (
                        getattr(state, "last_updated_at", None).isoformat()
                        if getattr(state, "last_updated_at", None) is not None
                        else None
                    ),
                }

        updated_at = getattr(trait_vector, "updated_at", None)
        return {
            "schema_version": getattr(trait_vector, "schema_version", None),
            "updated_at": updated_at.isoformat() if updated_at is not None else None,
            "traits": traits,
        }

    async def get_trait_vector(self, user_id: str) -> dict[str, Any] | None:
        core_profile = self._manager.get_profile(user_id)
        if core_profile is None:
            return None
        return {
            "user_id": user_id,
            "profile_version": core_profile.version,
            "last_update_source": core_profile.last_update_source,
            "last_update_trigger_conversation_id": core_profile.last_update_trigger_conversation_id,
            "trait_vector": self._trait_vector_to_dict(core_profile.trait_vector),
        }

    async def update_trait_vector_from_mappings(
        self,
        user_id: str,
        mappings: list[dict[str, Any]],
        *,
        source: str = "trait_mapping",
    ) -> dict[str, Any]:
        core_profile = self._manager.update_trait_vector_from_mappings(user_id, mappings, source=source)
        return {
            "user_id": user_id,
            "profile_version": core_profile.version,
            "last_update_source": core_profile.last_update_source,
            "last_update_trigger_conversation_id": core_profile.last_update_trigger_conversation_id,
            "trait_vector": self._trait_vector_to_dict(core_profile.trait_vector),
        }

    async def set_trait_frozen(
        self,
        user_id: str,
        trait_name: str,
        frozen: bool = True,
    ) -> dict[str, Any]:
        core_profile = self._manager.set_trait_frozen(user_id, trait_name, frozen)
        return {
            "user_id": user_id,
            "profile_version": core_profile.version,
            "trait_name": trait_name,
            "frozen": bool(frozen),
            "trait_vector": self._trait_vector_to_dict(core_profile.trait_vector),
        }

    async def rollback_profile(self, user_id: str, steps: int = 1) -> dict[str, Any] | None:
        core_profile = self._manager.rollback_profile(user_id, steps)
        if core_profile is None:
            return None
        return {
            "user_id": user_id,
            "profile_version": core_profile.version,
            "last_update_source": core_profile.last_update_source,
            "last_update_trigger_conversation_id": core_profile.last_update_trigger_conversation_id,
            "trait_vector": self._trait_vector_to_dict(core_profile.trait_vector),
        }

    async def rollback_profile_to_version(
        self,
        user_id: str,
        target_version: int,
    ) -> dict[str, Any] | None:
        core_profile = self._manager.rollback_profile_to_version(user_id, target_version)
        if core_profile is None:
            return None
        return {
            "user_id": user_id,
            "profile_version": core_profile.version,
            "last_update_source": core_profile.last_update_source,
            "last_update_trigger_conversation_id": core_profile.last_update_trigger_conversation_id,
            "trait_vector": self._trait_vector_to_dict(core_profile.trait_vector),
        }

    async def get_version_history(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        history = self._manager.get_version_history(user_id, limit)
        out: list[dict[str, Any]] = []
        for p in history:
            out.append(
                {
                    "user_id": p.user_id,
                    "profile_version": p.version,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                    "last_update_source": p.last_update_source,
                    "last_update_trigger_conversation_id": p.last_update_trigger_conversation_id,
                    "trait_vector": self._trait_vector_to_dict(p.trait_vector),
                }
            )
        return out

    async def list_new_trait_pool(
        self,
        user_id: str,
        *,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        tags = self._manager.list_tags(user_id, "new_trait_pool")
        out: list[dict[str, Any]] = []
        for tag in tags:
            value = tag.value
            if status is not None and isinstance(value, dict):
                if str(value.get("status") or "").strip() != status:
                    continue
            out.append(
                {
                    "trait_name": tag.name,
                    "value": value,
                    "created_at": tag.created_at.isoformat() if tag.created_at else None,
                    "updated_at": tag.updated_at.isoformat() if tag.updated_at else None,
                }
            )
        return out

    async def review_new_trait_candidate(
        self,
        user_id: str,
        trait_name: str,
        action: str,
        *,
        merged_into: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any] | None:
        action_norm = str(action or "").strip().lower()
        if action_norm not in {"approve", "reject", "ignore", "merge", "promote"}:
            raise ValueError("action must be one of: approve, reject, ignore, merge, promote")

        tag = self._manager.get_tag(user_id, "new_trait_pool", str(trait_name))
        if tag is None:
            return None

        payload: dict[str, Any] = {}
        if isinstance(tag.value, dict):
            payload.update(tag.value)

        review_history_raw = payload.get("review_history")
        review_history: list[dict[str, Any]] = []
        if isinstance(review_history_raw, list):
            review_history = [x for x in review_history_raw if isinstance(x, dict)]

        now_iso = datetime.now().isoformat()
        review_history.append(
            {
                "action": action_norm,
                "merged_into": str(merged_into) if merged_into else None,
                "note": str(note) if note else None,
                "reviewed_at": now_iso,
            }
        )
        review_history = review_history[-20:]

        if action_norm == "approve":
            payload["status"] = "approved"
        elif action_norm == "reject":
            payload["status"] = "rejected"
        elif action_norm == "ignore":
            payload["status"] = "ignored"
        elif action_norm == "merge":
            payload["status"] = "merged"
            if merged_into:
                payload["merged_into"] = str(merged_into)
        elif action_norm == "promote":
            payload["status"] = "promote_requested"
            if merged_into:
                payload["proposed_standard_trait"] = str(merged_into)

        payload["reviewed_at"] = datetime.now().isoformat()
        payload["review_action"] = action_norm
        if note:
            payload["review_note"] = str(note)

        payload["review_history"] = review_history

        merged_mapping_applied = False
        if action_norm == "merge" and merged_into:
            try:
                from user_profile.trait_schema import STANDARD_TRAITS
            except Exception:
                STANDARD_TRAITS = []

            if str(merged_into) in set(STANDARD_TRAITS):
                inferred_value = None
                confidence = None
                mapping_payload = payload.get("mapping")
                if isinstance(mapping_payload, dict):
                    inferred_value = mapping_payload.get("inferred_value")
                    confidence = mapping_payload.get("confidence")

                map_entry: dict[str, Any] = {
                    "action": "MAP",
                    "trait_name": str(trait_name),
                    "original_trait_name": str(trait_name),
                    "target_trait": str(merged_into),
                    "inferred_value": inferred_value if inferred_value is not None else 0.5,
                    "confidence": confidence if confidence is not None else 0.8,
                    "reason": f"merged from new_trait_pool: {trait_name}",
                }
                self._manager.update_trait_vector_from_mappings(
                    user_id,
                    [map_entry],
                    source="new_trait_pool_merge",
                )
                merged_mapping_applied = True

        updated = self._manager.upsert_tag(user_id, "new_trait_pool", str(trait_name), payload)
        return {
            "trait_name": updated.name,
            "value": updated.value,
            "created_at": updated.created_at.isoformat() if updated.created_at else None,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None,
            "merged_mapping_applied": merged_mapping_applied,
        }
    
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

    async def learn_new_traits(
        self,
        user_id: str,
        messages: list[Message] | None = None,
        selected_sentences: list[str] | None = None,
        provider: str | None = None,
        model: str | None = None,
        store: bool = True,
        map_to_standard: bool = True,
    ) -> dict[str, Any]:
        if self._llm_adapter is None:
            raise ValueError("LLM adapter not configured, cannot learn new traits")

        if selected_sentences is not None:
            if len(selected_sentences) < 10:
                raise ValueError("selected_sentences must contain at least 10 sentences")
            conversation_text = "\n".join([f"User selected: {s}" for s in selected_sentences])
        else:
            messages = messages or []
            if len(messages) < 10:
                raise ValueError("messages must contain at least 10 messages")
            conversation_text = self._format_conversation(messages)

        prompt = TRAIT_DISCOVERY_PROMPT.format(conversation=conversation_text)
        llm_call = LLMCall(
            task_type="persona",
            prompt=prompt,
            quality="normal",
            user_id=user_id,
            provider=provider,
            model=model,
        )

        result = await self._llm_adapter.call(llm_call)
        data = self._parse_json_object(result.text)

        general_traits = data.get("general_traits", [])
        personal_traits = data.get("personal_traits", [])

        mapping: list[dict[str, Any]] | None = None
        new_trait_candidates: list[dict[str, Any]] = []

        all_traits: list[dict[str, Any]] = []
        if isinstance(general_traits, list):
            all_traits.extend([t for t in general_traits if isinstance(t, dict)])
        if isinstance(personal_traits, list):
            all_traits.extend([t for t in personal_traits if isinstance(t, dict)])

        if map_to_standard and all_traits:
            mapping = await self.map_traits_to_standard(
                user_id=user_id,
                traits=all_traits,
                provider=provider,
                model=model,
            )

            mapping = [
                self._normalize_trait_mapping_entry(m)
                for m in mapping
                if isinstance(m, dict)
            ]

            for m in mapping:
                action = str(m.get("action") or "").upper()
                if action == "NEW" or m.get("mapped_to") == "new_trait_candidate" or m.get("suggestion") == "keep_new":
                    new_trait_candidates.append(m)

        if store and mapping:
            self._manager.update_trait_vector_from_mappings(user_id, mapping)

        if store:
            for t in general_traits:
                if isinstance(t, dict) and t.get("trait_name"):
                    self._manager.add_tag(
                        user_id,
                        "learned_traits/general",
                        str(t["trait_name"]),
                        t,
                    )
            for t in personal_traits:
                if isinstance(t, dict) and t.get("trait_name"):
                    self._manager.add_tag(
                        user_id,
                        "learned_traits/personal",
                        str(t["trait_name"]),
                        t,
                    )

            if mapping:
                for m in mapping:
                    if isinstance(m, dict) and m.get("trait_name"):
                        self._manager.add_tag(
                            user_id,
                            "learned_traits/mapping",
                            str(m["trait_name"]),
                            m,
                        )

            for cand in new_trait_candidates:
                trait_name = cand.get("trait_name")
                if not trait_name:
                    continue

                now_iso = datetime.now().isoformat()
                existing = self._manager.get_tag(user_id, "new_trait_pool", str(trait_name))
                existing_payload: dict[str, Any] = {}
                if existing is not None and isinstance(existing.value, dict):
                    existing_payload = dict(existing.value)

                first_seen = str(existing_payload.get("first_seen") or now_iso)
                current_count = 0
                try:
                    current_count = int(existing_payload.get("count", 0))
                except Exception:
                    current_count = 0

                example_users_raw = existing_payload.get("example_users")
                example_users: list[str] = []
                if isinstance(example_users_raw, list):
                    example_users = [str(x) for x in example_users_raw if str(x).strip()]
                if str(user_id) not in example_users:
                    example_users.append(str(user_id))
                example_users = example_users[-20:]

                sample_mappings_raw = existing_payload.get("sample_mappings")
                sample_mappings: list[dict[str, Any]] = []
                if isinstance(sample_mappings_raw, list):
                    sample_mappings = [x for x in sample_mappings_raw if isinstance(x, dict)]
                sample_mappings.append(dict(cand))
                sample_mappings = sample_mappings[-5:]

                review_history_raw = existing_payload.get("review_history")
                review_history: list[dict[str, Any]] = []
                if isinstance(review_history_raw, list):
                    review_history = [x for x in review_history_raw if isinstance(x, dict)]

                payload = {
                    "trait_name": str(trait_name),
                    "status": str(existing_payload.get("status") or "pending_review"),
                    "first_seen": first_seen,
                    "last_seen": now_iso,
                    "frequency": current_count + 1,
                    "example_users": example_users,
                    "candidate_merge_targets": existing_payload.get("candidate_merge_targets")
                    if isinstance(existing_payload.get("candidate_merge_targets"), list)
                    else [],
                    "sample_mappings": sample_mappings,
                    "review_history": review_history,
                    "mapping": cand,
                }

                self._manager.upsert_tag_with_incrementing_counter(
                    user_id,
                    "new_trait_pool",
                    str(trait_name),
                    payload,
                    counter_key="count",
                    delta=1,
                )

        return {
            "general_traits": general_traits,
            "personal_traits": personal_traits,
            "mapping": mapping,
            "new_trait_candidates": new_trait_candidates,
        }

    async def map_traits_to_standard(
        self,
        user_id: str,
        traits: list[dict[str, Any]],
        provider: str | None = None,
        model: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._llm_adapter is None:
            raise ValueError("LLM adapter not configured, cannot map traits")

        def _truncate(s: Any, max_len: int) -> str:
            text = str(s or "")
            if len(text) <= max_len:
                return text
            return text[: max_len - 1] + "…"

        compact_traits: list[dict[str, Any]] = []
        for t in traits[:15]:
            if not isinstance(t, dict):
                continue
            name = t.get("trait_name")
            if not name:
                continue
            compact_traits.append(
                {
                    "trait_name": _truncate(name, 24),
                    "description": _truncate(t.get("description"), 80),
                    "confidence": t.get("confidence"),
                }
            )

        prompt = TRAIT_MAPPING_PROMPT.format(
            standard_traits=json.dumps(CORE_STANDARD_TRAITS, ensure_ascii=False),
            traits_json=json.dumps(compact_traits, ensure_ascii=False),
        )
        llm_call = LLMCall(
            task_type="persona",
            prompt=prompt,
            quality="normal",
            user_id=user_id,
            provider=provider,
            model=model,
        )
        result = await self._llm_adapter.call(llm_call)
        parsed = self._parse_json_value(result.text)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        return []

    def _parse_json_value(self, response_text: str) -> Any:
        text = (response_text or "").strip()

        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()

        if "[" in text and "]" in text:
            start = text.find("[")
            end = text.rfind("]") + 1
            text = text[start:end]
        elif "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]

        try:
            return json.loads(text)
        except Exception:
            return None
    def _parse_json_object(self, response_text: str) -> dict[str, Any]:
        text = (response_text or "").strip()

        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()

        if "{" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]

        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _normalize_trait_mapping_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        action_raw = entry.get("action")
        if action_raw is not None:
            action = str(action_raw).upper()
            original_trait_name = entry.get("original_trait_name") or entry.get("trait_name")
            target_trait = entry.get("target_trait")
            new_trait_name = entry.get("new_trait_name")
            inferred_value = entry.get("inferred_value")

            mapped_to: str | None
            suggestion: str | None
            if action == "MAP":
                mapped_to = str(target_trait) if target_trait else None
                suggestion = "merge" if mapped_to else None
            elif action == "NEW":
                mapped_to = "new_trait_candidate"
                suggestion = "keep_new"
                if not new_trait_name and original_trait_name:
                    new_trait_name = str(original_trait_name)
            elif action == "DISCARD":
                mapped_to = None
                suggestion = "discard"
            else:
                mapped_to = None
                suggestion = None

            return {
                "trait_name": str(original_trait_name) if original_trait_name else "",
                "original_trait_name": str(original_trait_name) if original_trait_name else "",
                "action": action,
                "target_trait": target_trait,
                "new_trait_name": new_trait_name,
                "inferred_value": inferred_value,
                "confidence": entry.get("confidence"),
                "reason": entry.get("reason"),
                "mapped_to": mapped_to,
                "suggestion": suggestion,
            }

        trait_name = entry.get("trait_name")
        mapped_to_old = entry.get("mapped_to")
        suggestion_old = entry.get("suggestion")
        importance_old = entry.get("importance")
        reason_old = entry.get("reason")
        confidence_old = entry.get("confidence")
        inferred_value_old = entry.get("inferred_value")

        action: str
        target_trait: str | None = None
        new_trait_name: str | None = None
        mapped_to: str | None = None
        suggestion: str | None = None

        if mapped_to_old == "new_trait_candidate" or suggestion_old == "keep_new":
            action = "NEW"
            mapped_to = "new_trait_candidate"
            suggestion = "keep_new"
            new_trait_name = str(trait_name) if trait_name else None
        elif suggestion_old == "discard":
            action = "DISCARD"
            mapped_to = None
            suggestion = "discard"
        else:
            action = "MAP"
            target_trait = str(mapped_to_old) if mapped_to_old else None
            mapped_to = target_trait
            suggestion = "merge" if target_trait else None

        return {
            "trait_name": str(trait_name) if trait_name else "",
            "original_trait_name": str(trait_name) if trait_name else "",
            "action": action,
            "target_trait": target_trait,
            "new_trait_name": new_trait_name,
            "inferred_value": inferred_value_old,
            "confidence": confidence_old,
            "reason": reason_old,
            "mapped_to": mapped_to,
            "suggestion": suggestion,
            "importance": importance_old,
        }
    
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
