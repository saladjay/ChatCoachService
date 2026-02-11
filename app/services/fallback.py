"""
Fallback strategy service for error scenarios.

This module provides conservative template responses when the normal
generation flow fails. It ensures the system can always return a
reasonable response even in error conditions.

Requirements: 4.2, 4.4
"""

from typing import Literal

from app.models.schemas import (
    ContextResult,
    IntimacyCheckResult,
    LLMResult,
    PersonaSnapshot,
    SceneAnalysisResult,
)


class FallbackStrategy:
    """Provides fallback responses for error scenarios.
    
    Implements conservative template responses based on conversation scene
    and context. Used when:
    - Context building fails (Requirement 4.4)
    - Intimacy check fails after max retries (Requirement 4.2)
    - LLM calls timeout or fail
    
    Requirements: 4.2, 4.4
    """
    
    # Scene-based template responses
    SCENE_TEMPLATES: dict[str, str] = {
        "破冰": "我觉得我们可以慢慢聊，不着急。",
        "推进": "这个话题挺有意思的，你怎么看？",
        "冷却": "好的，我理解。",
        "维持": "嗯嗯，是这样的。",
    }
    
    # Default template when scene is unknown
    DEFAULT_TEMPLATE = "好的，我明白了。"
    
    # Emotion-based adjustments
    EMOTION_TEMPLATES: dict[str, str] = {
        "positive": "很高兴能和你聊天！",
        "negative": "我理解你的感受。",
        "neutral": "好的，我明白了。",
    }
    
    # Risk-aware templates (for high-risk situations)
    SAFE_TEMPLATES: list[str] = [
        "好的，我明白了。",
        "嗯嗯，是这样的。",
        "我理解。",
        "好的。",
    ]
    
    @classmethod
    def get_conservative_reply(
        cls, 
        scene: str | None = None,
        emotion_state: str | None = None,
        risk_flags: list[str] | None = None,
    ) -> str:
        """Get a conservative template reply based on context.
        
        Args:
            scene: The current conversation scene (破冰/推进/冷却/维持).
            emotion_state: Current emotion state (positive/negative/neutral).
            risk_flags: List of risk flags that may require extra caution.
        
        Returns:
            A safe, conservative reply text.
        
        Requirements: 4.2, 4.4
        """
        # If there are risk flags, use the safest possible response
        if risk_flags and len(risk_flags) > 0:
            return cls.SAFE_TEMPLATES[0]
        
        # Try scene-based template first
        if scene and scene in cls.SCENE_TEMPLATES:
            return cls.SCENE_TEMPLATES[scene]
        
        # Fall back to emotion-based template
        if emotion_state and emotion_state in cls.EMOTION_TEMPLATES:
            return cls.EMOTION_TEMPLATES[emotion_state]
        
        return cls.DEFAULT_TEMPLATE
    
    @classmethod
    def get_fallback_for_context_failure(cls) -> str:
        """Get fallback reply when context building fails.
        
        Returns the safest possible response since we have no context.
        
        Returns:
            A safe, generic reply text.
        
        Requirements: 4.4
        """
        return cls.DEFAULT_TEMPLATE
    
    @classmethod
    def get_fallback_for_retry_exhaustion(
        cls,
        scene: SceneAnalysisResult | None = None,
        context: ContextResult | None = None,
    ) -> str:
        """Get fallback reply when retry attempts are exhausted.
        
        Uses available context to provide the most appropriate fallback.
        
        Args:
            scene: Scene analysis result if available.
            context: Context result if available.
        
        Returns:
            A conservative reply text based on available context.
        
        Requirements: 4.2
        """
        scene_type = scene.scene if scene else None
        emotion_state = context.emotion_state if context else None
        risk_flags = context.risk_flags if context else None
        
        return cls.get_conservative_reply(
            scene=scene_type,
            emotion_state=emotion_state,
            risk_flags=risk_flags,
        )
    
    @classmethod
    def create_fallback_llm_result(
        cls,
        scene: str | None = None,
        context: ContextResult | None = None,
    ) -> LLMResult:
        """Create a fallback LLMResult for error scenarios.
        
        Args:
            scene: The conversation scene if known.
            context: The context result if available.
        
        Returns:
            LLMResult with fallback content and zero cost.
        """
        emotion_state = context.emotion_state if context else None
        risk_flags = context.risk_flags if context else None
        
        return LLMResult(
            text=cls.get_conservative_reply(
                scene=scene,
                emotion_state=emotion_state,
                risk_flags=risk_flags,
            ),
            provider="fallback",
            model="template",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )
    
    @classmethod
    def create_fallback_intimacy_result(cls) -> IntimacyCheckResult:
        """Create a fallback IntimacyCheckResult.
        
        Fallback responses are always considered to pass intimacy check
        since they are designed to be safe and conservative.
        
        Returns:
            IntimacyCheckResult indicating passed with fallback reason.
        """
        return IntimacyCheckResult(
            passed=True,
            score=1.0,
            scores=[],
            reason="Fallback response - always safe",
        )
    
    @classmethod
    def create_default_scene(cls) -> SceneAnalysisResult:
        """Create a default scene analysis result for fallback scenarios.
        
        Returns:
            SceneAnalysisResult with safe default values.
        """
        return SceneAnalysisResult(
            scene="维持",
            intimacy_level=3,
            risk_flags=[],
        )
    
    @classmethod
    def create_default_persona(cls) -> PersonaSnapshot:
        """Create a default persona snapshot for fallback scenarios.
        
        Returns:
            PersonaSnapshot with conservative default values.
        """
        return PersonaSnapshot(
            style="克制",
            pacing="slow",
            risk_tolerance="low",
            confidence=0.5,
        )
    
    @classmethod
    def create_default_context(cls) -> ContextResult:
        """Create a default context result for fallback scenarios.
        
        Returns:
            ContextResult with safe default values.
        """
        return ContextResult(
            conversation_summary="Unable to build context",
            emotion_state="neutral",
            current_intimacy_level=3,
            risk_flags=[],
        )
