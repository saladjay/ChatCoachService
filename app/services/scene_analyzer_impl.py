from app.models.schemas import (
    SceneAnalysisInput,
    SceneAnalysisResult,
)
from app.services.base import (
    BaseSceneAnalyzer,
)


class SceneAnalyzer(BaseSceneAnalyzer):
    """Mock implementation of scene analysis service.
    
    Returns default scene analysis values for development and testing.
    """
    def __init__(self, llm_adapter: BaseLLMAdapter, provider: str | None = None, model: str | None = None):
        """Initialize ContextBuilder with LLM adapter.
        
        Args:
            llm_adapter: LLM adapter for analyzing conversation context
            provider: Optional LLM provider (e.g., "dashscope", "openai")
            model: Optional LLM model name
        """
        self._llm_adapter = llm_adapter
        self.provider = provider
        self.model = model

    async def analyze_scene(self, input: SceneAnalysisInput) -> SceneAnalysisResult:
        """Analyze scene with mock default values.
        
        Args:
            input: Scene analysis input (used for reference).
        
        Returns:
            SceneAnalysisResult with reasonable default values.
        """
        return SceneAnalysisResult(
            scene="维持",
            intimacy_level=3,
            risk_flags=[],
        )