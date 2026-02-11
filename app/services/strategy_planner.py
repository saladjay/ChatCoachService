"""Strategy Planning Service for Token Optimization.

This service implements the Prompt Layering pattern by separating strategy
planning from reply generation. Instead of including all strategy information
in the reply generation prompt, we first plan strategies in a separate,
focused step.

Token Savings: 20-30% additional reduction through prompt layering.

Architecture:
    SceneAnalyzer → StrategyPlanner → ReplyGenerator
    
    1. SceneAnalyzer: Analyzes conversation context (~270 tokens)
    2. StrategyPlanner: Plans specific strategies (~190 tokens)
    3. ReplyGenerator: Generates replies using plan (~720 tokens)
    
    Total: ~1180 tokens (vs ~1800 tokens without layering)
"""

from dataclasses import dataclass
from typing import Optional
import json

from app.services.llm_adapter import BaseLLMAdapter, LLMCall
from app.models.schemas import SceneAnalysisResult
from app.models.schemas_compact import StrategyPlanCompact
from app.services.schema_expander import SchemaExpander
from app.services.prompt_manager import get_prompt_manager, PromptType, PromptVersion
from user_profile.intimacy import intimacy_label_en


@dataclass
class StrategyPlanInput:
    """Input for strategy planning.
    
    Attributes:
        scene: Scene analysis result with recommended scenario
        conversation_summary: Brief conversation summary
        intimacy_level: User's target intimacy level (0-100)
        current_intimacy_level: Current conversation intimacy (0-100)
    """
    scene: SceneAnalysisResult
    conversation_summary: str
    intimacy_level: int
    current_intimacy_level: int


@dataclass
class StrategyPlanOutput:
    """Output from strategy planning.
    
    Attributes:
        recommended_scenario: Recommended scenario code (S/B/R/C/N)
        strategy_weights: Dict of strategy -> weight (0-1)
        avoid_strategies: List of strategies to avoid
        reasoning: Brief explanation of the plan
    """
    recommended_scenario: str
    strategy_weights: dict[str, float]
    avoid_strategies: list[str]
    reasoning: str = ""


class StrategyPlanner:
    """Plans conversation strategies based on scene analysis.
    
    This service implements the second stage of the 3-stage pipeline:
    1. SceneAnalyzer: Analyzes context
    2. StrategyPlanner: Plans strategies (THIS SERVICE)
    3. ReplyGenerator: Generates replies
    
    By separating strategy planning, we reduce the prompt size for reply
    generation and make the system more modular.
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        provider: str | None = None,
        model: str | None = None,
        use_compact: bool = True
    ):
        """Initialize StrategyPlanner.
        
        Args:
            llm_adapter: LLM adapter for making API calls
            provider: LLM provider (default: dashscope)
            model: LLM model (default: qwen-flash)
            use_compact: Use compact output format (default: True)
        """
        self._llm_adapter = llm_adapter
        self.provider = provider
        self.model = model
        self.use_compact = use_compact
        self._prompt_manager = get_prompt_manager()
    
    async def plan_strategies(self, input: StrategyPlanInput) -> StrategyPlanOutput:
        """Plan conversation strategies based on scene analysis.
        
        Args:
            input: Strategy plan input with scene and context
        
        Returns:
            Strategy plan with weights and recommendations
        """
        # Build ultra-compact prompt
        prompt = self._build_prompt(input)
        
        # Call LLM
        llm_call = LLMCall(
            task_type="strategy_planning",
            prompt=prompt,
            quality="normal",
            user_id="system",
            provider=self.provider,
            model=self.model,
            max_tokens=200  # Limit output to prevent excessive token usage
        )
        
        result = await self._llm_adapter.call(llm_call)
        
        # Parse response
        return self._parse_response(result.text, input)
    
    def _build_prompt(self, input: StrategyPlanInput) -> str:
        """Build ultra-compact strategy planning prompt.
        
        This prompt is designed to be minimal while still providing enough
        context for effective strategy planning.
        
        Target: ~190 tokens
        
        Args:
            input: Strategy plan input
        
        Returns:
            Compact prompt string
        """
        scene = input.scene
        target_label = intimacy_label_en(int(input.intimacy_level))
        current_label = intimacy_label_en(int(input.current_intimacy_level))
        
        if self.use_compact:
            prompt_template = self._prompt_manager.get_prompt_version(
                PromptType.STRATEGY_PLANNING,
                PromptVersion.V2_COMPACT,
            )
            prompt_template = (prompt_template or "").strip()
            prompt = prompt_template.format(
                recommended_scenario=scene.recommended_scenario,
                recommended_strategies=", ".join(scene.recommended_strategies[:3]),
                target_label=target_label,
                intimacy_level=input.intimacy_level,
                current_label=current_label,
                current_intimacy_level=input.current_intimacy_level,
                conversation_summary=input.conversation_summary[:100],
            )
        else:
            prompt_template = self._prompt_manager.get_prompt_version(
                PromptType.STRATEGY_PLANNING,
                PromptVersion.V1_ORIGINAL,
            )
            prompt_template = (prompt_template or "").strip()
            prompt = prompt_template.format(
                recommended_scenario=scene.recommended_scenario,
                recommended_strategies=", ".join(scene.recommended_strategies),
                target_label=target_label,
                intimacy_level=input.intimacy_level,
                current_label=current_label,
                current_intimacy_level=input.current_intimacy_level,
                conversation_summary=input.conversation_summary,
            )
        
        return prompt
    
    def _parse_response(self, response_text: str, input: StrategyPlanInput) -> StrategyPlanOutput:
        """Parse LLM response to extract strategy plan.
        
        Args:
            response_text: LLM response text
            input: Original input for fallback
        
        Returns:
            Strategy plan output
        """
        text = response_text.strip()
        
        # Handle markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()
        
        # Extract JSON object
        if "{" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]
        
        try:
            data = json.loads(text)
            
            if self.use_compact:
                # Parse compact format
                compact = StrategyPlanCompact(**data)
                expanded = SchemaExpander.expand_strategy_plan(compact)
                
                return StrategyPlanOutput(
                    recommended_scenario=expanded["recommended_scenario"],
                    strategy_weights=expanded["strategy_weights"],
                    avoid_strategies=expanded["avoid_strategies"],
                    reasoning=""
                )
            else:
                # Parse standard format
                return StrategyPlanOutput(
                    recommended_scenario=data.get("recommended_scenario", input.scene.recommended_scenario),
                    strategy_weights=data.get("strategy_weights", {}),
                    avoid_strategies=data.get("avoid_strategies", []),
                    reasoning=data.get("reasoning", "")
                )
        
        except (json.JSONDecodeError, ValueError, Exception) as e:
            # Fallback: Use scene analysis recommendations
            # Create equal weights for recommended strategies
            weights = {}
            for i, strategy in enumerate(input.scene.recommended_strategies[:3]):
                weights[strategy] = 1.0 - (i * 0.1)  # 1.0, 0.9, 0.8
            
            return StrategyPlanOutput(
                recommended_scenario=input.scene.recommended_scenario,
                strategy_weights=weights,
                avoid_strategies=[],
                reasoning="Fallback: Using scene analysis recommendations"
            )
