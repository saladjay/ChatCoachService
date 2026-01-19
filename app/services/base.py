"""Abstract base classes for all sub-module services.

This module defines the abstract interfaces for:
- BaseContextBuilder: Context building service
- BaseSceneAnalyzer: Scene analysis service
- BasePersonaInferencer: Persona inference service
- BaseReplyGenerator: Reply generation service
- BaseIntimacyChecker: Intimacy check service

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

from abc import ABC, abstractmethod

from app.models.schemas import (
    ContextBuilderInput,
    ContextResult,
    IntimacyCheckInput,
    IntimacyCheckResult,
    LLMResult,
    PersonaInferenceInput,
    PersonaSnapshot,
    ReplyGenerationInput,
    SceneAnalysisInput,
    SceneAnalysisResult,
)


class BaseContextBuilder(ABC):
    """Abstract base class for context building service.
    
    Responsible for integrating historical dialogue, emotion trends,
    and other information to build context for downstream services.
    
    Requirements: 3.5
    """

    @abstractmethod
    async def build_context(self, input: ContextBuilderInput) -> ContextResult:
        """Build context from conversation history and emotion data.
        
        Args:
            input: Context builder input containing user_id, target_id,
                   conversation_id, history_dialog, and emotion_trend.
        
        Returns:
            ContextResult containing conversation_summary, emotion_state,
            current_intimacy_level, and risk_flags.
        """
        ...


class BaseSceneAnalyzer(ABC):
    """Abstract base class for scene analysis service.
    
    Analyzes the current conversation scene and intimacy level.
    
    Requirements: 3.1
    """

    @abstractmethod
    async def analyze_scene(self, input: SceneAnalysisInput) -> SceneAnalysisResult:
        """Analyze the current conversation scene.
        
        Args:
            input: Scene analysis input containing conversation_id,
                   history_dialog, and emotion_trend.
        
        Returns:
            SceneAnalysisResult containing scene type (破冰/推进/冷却/维持),
            intimacy_level (1-5), and risk_flags.
        """
        ...


class BasePersonaInferencer(ABC):
    """Abstract base class for persona inference service.
    
    Infers user style preferences and characteristics.
    
    Requirements: 3.2
    """

    @abstractmethod
    async def infer_persona(self, input: PersonaInferenceInput) -> PersonaSnapshot:
        """Infer user persona from conversation data.
        
        Args:
            input: Persona inference input containing user_id,
                   conversation_id, scene, and history_dialog.
        
        Returns:
            PersonaSnapshot containing style, pacing, risk_tolerance,
            and confidence score.
        """
        ...


class BaseReplyGenerator(ABC):
    """Abstract base class for reply generation service.
    
    Generates suggested replies using LLM.
    
    Requirements: 3.3
    """

    @abstractmethod
    async def generate_reply(self, input: ReplyGenerationInput) -> LLMResult:
        """Generate a reply using LLM.
        
        Args:
            input: Reply generation input containing prompt, quality,
                   context, scene, and persona.
        
        Returns:
            LLMResult containing generated text, provider, model,
            token counts, and cost.
        """
        ...


class BaseIntimacyChecker(ABC):
    """Abstract base class for intimacy check service.
    
    Validates whether a reply is appropriate for the current
    relationship stage.
    
    Requirements: 3.4
    """

    @abstractmethod
    async def check(self, input: IntimacyCheckInput) -> IntimacyCheckResult:
        """Check if reply is appropriate for current intimacy level.
        
        Args:
            input: Intimacy check input containing reply_text,
                   intimacy_level, and persona.
        
        Returns:
            IntimacyCheckResult containing passed status, score,
            and optional reason for failure.
        """
        ...
