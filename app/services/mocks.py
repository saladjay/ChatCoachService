"""Mock implementations for all sub-module services.

This module provides Mock implementations that return reasonable default values,
enabling development and testing without real service implementations.

Requirements: 7.4
"""

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
from app.services.base import (
    BaseContextBuilder,
    BaseIntimacyChecker,
    BasePersonaInferencer,
    BaseReplyGenerator,
    BaseSceneAnalyzer,
)


class MockContextBuilder(BaseContextBuilder):
    """Mock implementation of context builder service.
    
    Returns default context values for development and testing.
    """

    async def build_context(self, input: ContextBuilderInput) -> ContextResult:
        """Build mock context with default values.
        
        Args:
            input: Context builder input (used for conversation_id reference).
        
        Returns:
            ContextResult with reasonable default values.
        """
        return ContextResult(
            conversation_summary="Mock conversation summary",
            emotion_state="neutral",
            current_intimacy_level=3,
            risk_flags=[],
        )


class MockSceneAnalyzer(BaseSceneAnalyzer):
    """Mock implementation of scene analysis service.
    
    Returns default scene analysis values for development and testing.
    """

    async def analyze_scene(self, input: SceneAnalysisInput) -> SceneAnalysisResult:
        """Analyze scene with mock default values.
        
        Args:
            input: Scene analysis input (used for reference).
        
        Returns:
            SceneAnalysisResult with reasonable default values.
        """
        return SceneAnalysisResult(
            relationship_state="维持",
            scenario="BALANCED",
            intimacy_level=3,  # 使用 1-5 的范围
            risk_flags=[],
        )


class MockPersonaInferencer(BasePersonaInferencer):
    """Mock implementation of persona inference service.
    
    Returns default persona values for development and testing.
    """

    async def infer_persona(self, input: PersonaInferenceInput) -> PersonaSnapshot:
        """Infer persona with mock default values.
        
        Args:
            input: Persona inference input (used for reference).
        
        Returns:
            PersonaSnapshot with reasonable default values.
        """
        return PersonaSnapshot(
            style="理性",
            pacing="normal",
            risk_tolerance="medium",
            confidence=0.8,
            prompt="Mock persona prompt for testing",
        )


class MockReplyGenerator(BaseReplyGenerator):
    """Mock implementation of reply generation service.
    
    Returns default LLM result values for development and testing.
    """

    async def generate_reply(self, input: ReplyGenerationInput) -> LLMResult:
        """Generate mock reply with default values.
        
        Args:
            input: Reply generation input (quality affects mock model selection).
        
        Returns:
            LLMResult with reasonable default values.
        """
        # Select mock model based on quality tier
        model_map = {
            "cheap": "gpt-3.5-turbo",
            "normal": "gpt-4",
            "premium": "gpt-4-turbo",
        }
        model = model_map.get(input.quality, "gpt-4")
        
        # Mock cost based on quality
        cost_map = {
            "cheap": 0.001,
            "normal": 0.01,
            "premium": 0.03,
        }
        cost = cost_map.get(input.quality, 0.01)
        
        return LLMResult(
            text="这是一个模拟回复，用于开发和测试。",
            provider="openai",
            model=model,
            input_tokens=100,
            output_tokens=50,
            cost_usd=cost,
        )


class MockIntimacyChecker(BaseIntimacyChecker):
    """Mock implementation of intimacy check service.
    
    Returns default check result values for development and testing.
    """

    async def check(self, input: IntimacyCheckInput) -> IntimacyCheckResult:
        """Check intimacy with mock default values.
        
        Args:
            input: Intimacy check input (used for reference).
        
        Returns:
            IntimacyCheckResult with reasonable default values (always passes).
        """
        return IntimacyCheckResult(
            passed=True,
            score=0.85,
            reason=None,
        )
