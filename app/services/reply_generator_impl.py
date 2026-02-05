from app.models.schemas import (
    LLMResult,
    ReplyGenerationInput,
)
from app.services.base import BaseReplyGenerator
from app.services.llm_adapter import BaseLLMAdapter, LLMCall
from app.services.user_profile_impl import BaseUserProfileService
from app.services.prompt_assembler import PromptAssembler, REPLY_LENGTH_CONSTRAINTS
from app.services.schema_expander import SchemaExpander, parse_and_expand_reply_generation
from app.models.schemas_compact import ReplyGenerationCompact
from app.core.config import PromptConfig, settings
from typing import Optional
import json


class LLMAdapterReplyGenerator(BaseReplyGenerator):
    """Reply generator implementation using LLM Adapter.
    
    This class wraps the LLM Adapter to implement the BaseReplyGenerator interface,
    allowing it to be used by the Orchestrator.
    
    Requirements: 3.3
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        user_profile_service: BaseUserProfileService,
        user_id: str = "system",
        use_compact_prompt: bool = True,
        use_compact_v2: bool = True,
        strategy_planner: Optional['StrategyPlanner'] = None,
        prompt_config: Optional[PromptConfig] = None,  # Phase 3
    ):

        """Initialize with an LLM Adapter.
        
        Args:
            llm_adapter: The LLM adapter to use for generating replies.
            user_profile_service: User profile service for persona information.
            user_id: Default user ID for billing/logging.
            use_compact_prompt: Use compact prompt to reduce tokens (default: True).
            use_compact_v2: Use compact V2 with compact output codes (default: True).
            strategy_planner: Optional strategy planner for Phase 2 optimization.
            prompt_config: Optional prompt configuration for Phase 3 optimization.
        """
        self.llm_adapter = llm_adapter
        self.user_id = user_id
        self.user_profile_service = user_profile_service
        self.use_compact_v2 = use_compact_v2
        self.strategy_planner = strategy_planner
        
        # Phase 3: Use prompt config or defaults
        self.prompt_config = prompt_config or PromptConfig.from_env()
        
        self._prompt_assembler = PromptAssembler(
            user_profile_service, 
            use_compact_prompt=use_compact_prompt,
            use_compact_v2=use_compact_v2,
            include_reasoning=self.prompt_config.include_reasoning,  # Phase 3
        )

    async def generate_reply(self, input: ReplyGenerationInput) -> LLMResult:

        """Generate a reply using the LLM Adapter.
        
        Args:
            input: Reply generation input containing prompt, quality, context, etc.
        
        Returns:
            LLMResult with generated reply and metadata.
        """
        # Phase 2: 如果有 strategy_planner，先规划策略
        strategy_plan = None
        if (not settings.no_strategy_planner) and self.strategy_planner and input.scene and input.context:
            from app.services.strategy_planner import StrategyPlanInput
            
            plan_input = StrategyPlanInput(
                scene=input.scene,
                conversation_summary=input.context.conversation_summary or "",
                intimacy_level=input.scene.intimacy_level,
                current_intimacy_level=input.context.current_intimacy_level
            )
            strategy_plan = await self.strategy_planner.plan_strategies(plan_input)
        
        # 组装 prompt（如果有策略计划，会使用它来减少 prompt 大小）
        prompt = await self._prompt_assembler.assemble_reply_prompt(input, strategy_plan)
        
        # Phase 3: Get max_tokens from length constraints
        length_constraint = REPLY_LENGTH_CONSTRAINTS.get(input.quality, REPLY_LENGTH_CONSTRAINTS["normal"])
        max_tokens = length_constraint["max_tokens"]
        
        # Phase 3: Override with config if specified
        if self.prompt_config.max_reply_tokens:
            max_tokens = self.prompt_config.max_reply_tokens
        
        # Create LLM call
        llm_call = LLMCall(
            task_type="generation",
            prompt=prompt,
            quality=input.quality,
            user_id=input.user_id,
            max_tokens=max_tokens,  # Phase 3: Add token limit
        )
        
        result = await self.llm_adapter.call(llm_call)
        
        # 如果使用紧凑 V2，需要扩展输出
        if self.use_compact_v2:
            result = self._expand_compact_result(result)
        
        return result
    
    def _expand_compact_result(self, result: LLMResult) -> LLMResult:
        """Expand compact LLM result to full format.
        
        This method parses the compact JSON output and expands it to the
        standard reply format expected by the application.
        
        Args:
            result: LLM result with compact JSON text
        
        Returns:
            LLM result with expanded JSON text
        """
        try:
            text = result.text.strip()
            
            # Remove markdown code blocks if present
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                if end > start:
                    text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                if end > start:
                    text = text[start:end].strip()
            
            # Extract JSON object if there's extra text
            if "{" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                if end > start:
                    text = text[start:end]
            
            # Parse compact JSON
            data = json.loads(text)
            compact = ReplyGenerationCompact(**data)
            
            # Use SchemaExpander to expand
            expanded = SchemaExpander.expand_reply_generation(compact)
            
            # Convert back to JSON string
            expanded_json = json.dumps(expanded, ensure_ascii=False, indent=2)
            
            # Create new LLMResult
            return LLMResult(
                text=expanded_json,
                model=result.model,
                provider=result.provider,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=result.cost_usd,
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            # Parse failed, log and return original result
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to expand compact result: {e}. Returning original result.")
            return result
        except Exception as e:
            # Unexpected error, log and return original result
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error expanding compact result: {e}", exc_info=True)
            return result