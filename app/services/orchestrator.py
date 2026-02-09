"""Orchestrator service for coordinating the conversation generation flow.

This module implements the central orchestration logic that:
- Coordinates sub-module calls in sequence
- Handles retry logic for intimacy check failures
- Implements fallback strategies for errors
- Tracks execution time and costs

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.2, 4.3, 4.4, 4.5
"""
import traceback
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal

from app.core.config import OrchestratorConfig as OrchestratorConfigSettings
from app.core.config import settings
from app.core.config import BillingConfig
from app.core.exceptions import (
    ContextBuildError,
    OrchestrationError,
    QuotaExceededError,
    RetryExhaustedError,
)
from app.models.api import GenerateReplyRequest, GenerateReplyResponse
from app.models.schemas import (
    ContextBuilderInput,
    ContextResult,
    IntimacyCheckInput,
    LLMCallRecord,
    LLMResult,
    OrchestratorConfig,
    PersonaInferenceInput,
    PersonaSnapshot,
    ReplyGenerationInput,
    SceneAnalysisInput,
    SceneAnalysisResult,
    Message,
)
from app.services.base import (
    BaseContextBuilder,
    BaseIntimacyChecker,
    BasePersonaInferencer,
    BaseReplyGenerator,
    BaseSceneAnalyzer,
)
from app.services.billing import BillingService
from app.services.fallback import FallbackStrategy
from app.services.persistence import PersistenceService
from app.services.session_categorized_cache_service import SessionCategorizedCacheService

from app.observability.trace_logger import trace_logger

logger = logging.getLogger(__name__)


@dataclass
class StepExecutionLog:
    """Log entry for a single step execution."""
    step_name: str
    status: Literal["success", "failed", "skipped"]
    duration_ms: int
    error: str | None = None


@dataclass
class ExecutionContext:
    """Context for tracking execution state during generation."""
    user_id: str
    conversation_id: str
    quality: Literal["cheap", "normal", "premium"]
    accumulated_cost: float = 0.0
    step_logs: list[StepExecutionLog] = field(default_factory=list)
    billing_records: list[LLMCallRecord] = field(default_factory=list)
    forced_cheap: bool = False


class Orchestrator:
    """Central orchestration service for conversation generation.
    
    Coordinates the flow: Context_Builder → Scene_Analysis → 
    Persona_Inference → Reply_Generation → Intimacy_Check
    
    Implements retry logic, fallback strategies, and cost tracking.
    """

    def __init__(
        self,
        context_builder: BaseContextBuilder,
        scene_analyzer: BaseSceneAnalyzer,
        persona_inferencer: BasePersonaInferencer,
        reply_generator: BaseReplyGenerator,
        intimacy_checker: BaseIntimacyChecker,
        billing_service: BillingService,
        persistence_service: PersistenceService | None = None,
        cache_service: SessionCategorizedCacheService | None = None,
        config: OrchestratorConfig | None = None,
        billing_config: BillingConfig | None = None,
        strategy_planner: 'StrategyPlanner | None' = None,
    ):
        """Initialize the orchestrator with all required services.
        
        Args:
            context_builder: Service for building conversation context.
            scene_analyzer: Service for analyzing conversation scene.
            persona_inferencer: Service for inferring user persona.
            reply_generator: Service for generating replies.
            intimacy_checker: Service for checking reply appropriateness.
            billing_service: Service for tracking costs.
            persistence_service: Optional service for persisting conversation summaries.
            cache_service: Optional service for caching categorized events.
            config: Orchestrator configuration (retry, timeout settings).
            billing_config: Billing configuration (cost limits).
            strategy_planner: Optional strategy planner for Phase 2 optimization.
        """
        self.context_builder = context_builder
        self.scene_analyzer = scene_analyzer
        self.persona_inferencer = persona_inferencer
        self.reply_generator = reply_generator
        self.intimacy_checker = intimacy_checker
        self.billing_service = billing_service
        self.persistence_service = persistence_service
        self.cache_service = cache_service

        self.config = config or OrchestratorConfig()
        self.billing_config = billing_config or BillingConfig()
        self.strategy_planner = strategy_planner


    async def scenario_analysis(
        self,
        request: GenerateReplyRequest
    ) -> SceneAnalysisResult:
        """Analyze the conversation scenario.
        Flow: Context_Builder → Scene_Analysis

        """
        if not await self.billing_service.check_quota(request.user_id):
            logger.warning(f"Quota exceeded for user {request.user_id}")
            raise QuotaExceededError(
                message=f"User {request.user_id} has exceeded their quota",
                user_id=request.user_id,
            )
        
        # Initialize execution context
        exec_ctx = ExecutionContext(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            quality=request.quality,
        )
        
        try:
            # Step 1: Build context
            cached_context = await self._get_cached_payload(request, "context_analysis")
            if cached_context:
                context = ContextResult(**cached_context)
            else:
                context = await self._execute_step(
                    exec_ctx,
                    "context_builder",
                    self._build_context,
                    request,
                )
                await self._append_cache_event(request, "context_analysis", context.model_dump(mode="json"))
            
            # Step 2: Analyze scene (传递 context 以获取当前亲密度)
            cached_scene = await self._get_cached_payload(request, "scene_analysis")
            if cached_scene:
                scene = SceneAnalysisResult(**cached_scene)
            else:
                scene = await self._execute_step(
                    exec_ctx,
                    "scene_analysis",
                    self._analyze_scene,
                    request,
                    context,  # 传递 context
                )
                await self._append_cache_event(request, "scene_analysis", scene.model_dump(mode="json"))
            return scene
            
        except ContextBuildError as e:
            # Fallback for context build failure (Requirement 4.4)
            logger.error(f"Context build failed: {e}")
            # Return a fallback SceneAnalysisResult instead of GenerateReplyResponse
            return self._create_fallback_scene_analysis()
            
        except Exception as e:
            # Log error and return friendly response (Requirement 4.5)
            logger.exception(f"Orchestration error: {e}")
            raise OrchestrationError(
                message="An error occurred during generation",
                original_error=e,
            ) from e

    async def merge_step_analysis(
        self,
        request: GenerateReplyRequest,
        image_url: str,
        image_base64: str,
        image_width: int,
        image_height: int,
    ) -> tuple[ContextResult, SceneAnalysisResult]:
        """
        Perform merged analysis using merge_step prompt.
        
        This function combines screenshot parsing, context building, and scenario analysis
        into a single LLM call for improved performance.
        
        Flow: Single LLM call → Parse output → Apply strategy selection → Cache results
        
        Args:
            request: GenerateReplyRequest with user info
            image_url: Original image URL (used when image_format=url)
            image_base64: Base64-encoded screenshot image (used when image_format=base64)
            image_width: Image width in pixels
            image_height: Image height in pixels
            
        Returns:
            Tuple of (ContextResult, SceneAnalysisResult)
            
        Raises:
            QuotaExceededError: If user quota is exceeded
            OrchestrationError: For other orchestration failures
        """
        if not await self.billing_service.check_quota(request.user_id):
            logger.warning(f"Quota exceeded for user {request.user_id}")
            raise QuotaExceededError(
                message=f"User {request.user_id} has exceeded their quota",
                user_id=request.user_id,
            )
        
        # Initialize execution context
        exec_ctx = ExecutionContext(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            quality=request.quality,
        )
        
        try:
            # Check cache first using traditional field names for cache sharing
            cached_context = await self._get_cached_payload(request, "context_analysis")
            cached_scene = await self._get_cached_payload(request, "scene_analysis")
            
            if cached_context and cached_scene:
                logger.info("Using cached merge_step results (from traditional cache)")
                context = ContextResult(**cached_context)
                scene = SceneAnalysisResult(**cached_scene)
                return context, scene
            
            # No cache, perform merge_step analysis
            logger.info("Performing merge_step analysis with LLM")
            
            # Get merge_step prompt
            from app.services.prompt_manager import get_prompt_manager, PromptType, PromptVersion
            pm = get_prompt_manager()
            prompt = pm.get_prompt_version(PromptType.MERGE_STEP, PromptVersion.V1_ORIGINAL)
            
            if not prompt:
                logger.error("merge_step prompt not found, falling back to separate calls")
                raise ValueError("merge_step prompt not available")
            
            # Call LLM with merge_step prompt
            from app.services.llm_adapter import create_llm_adapter, LLMCall
            llm_adapter = create_llm_adapter()
            
            step_id = uuid.uuid4().hex
            llm_start_time = time.time()
            
            trace_logger.log_event({
                "level": "debug",
                "type": "step_start",
                "step_id": step_id,
                "step_name": "merge_step_llm",
                "task_type": "merge_step",
                "session_id": request.conversation_id,
                "user_id": request.user_id,
            })
            
            # Call multimodal LLM with race strategy
            from app.services.screenshot_parser import ScreenshotParserService
            from app.core.config import settings
            
            # Get image format configuration
            image_format = settings.llm.multimodal_image_format
            
            # Choose image data and type based on configuration
            if image_format == "url":
                image_data = image_url
                image_type = "url"
                logger.info(f"Using URL format for merge_step")
            else:
                image_data = image_base64
                image_type = "base64"
                logger.info(f"Using base64 format for merge_step")
            
            # Log prompt if enabled
            if trace_logger.should_log_prompt():
                trace_logger.log_event({
                    "level": "debug",
                    "type": "llm_prompt",
                    "step_id": step_id,
                    "step_name": "merge_step_llm",
                    "task_type": "merge_step",
                    "session_id": request.conversation_id,
                    "user_id": request.user_id,
                    "prompt": prompt,
                    "image_size": f"{image_width}x{image_height}",
                })
            
            # Create a temporary parser instance to use race strategy
            from app.services.image_fetcher import ImageFetcher
            from app.services.prompt_manager import PromptManager
            from app.services.result_normalizer import ResultNormalizer
            
            temp_parser = ScreenshotParserService(
                image_fetcher=ImageFetcher(),
                prompt_manager=PromptManager(),
                llm_adapter=llm_adapter,
                result_normalizer=ResultNormalizer(),
            )
            
            # Define validator for merge_step results
            from app.services.merge_step_adapter import MergeStepAdapter
            merge_adapter = MergeStepAdapter()
            
            def validate_merge_step_result(parsed_json: dict) -> bool:
                """Check if result has valid merge_step structure."""
                return merge_adapter.validate_merge_output(parsed_json)
            
            try:
                winning_strategy, llm_result = await temp_parser._race_multimodal_calls(
                    prompt=prompt,
                    image_data=image_data,
                    image_type=image_type,
                    mime_type="image/jpeg",
                    user_id=request.user_id,
                    session_id=request.conversation_id,
                    provider=settings.llm.default_provider,
                    validator=validate_merge_step_result,
                    task_name="merge_step",
                )
                
                # Parse JSON from winning result
                import json
                from app.api.v1.predict import parse_json_with_markdown
                
                try:
                    parsed_json = parse_json_with_markdown(llm_result.text)
                    raw_text = llm_result.text
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from merge_step: {e}")
                    raise RuntimeError(f"Failed to parse JSON: {str(e)}")
            except ValueError as e:
                # This catches the "Both calls failed" error from race strategy
                error_msg = str(e)
                logger.error(f"Merge_step race failed: {error_msg}")
                raise RuntimeError(f"merge_step analysis failed: {error_msg}")
            except RuntimeError as e:
                error_msg = str(e)
                # Enhanced error logging for JSON parsing failures
                if "Failed to parse JSON" in error_msg:
                    logger.error(
                        f"JSON parsing failed in merge_step analysis. "
                        f"The LLM returned invalid or incomplete JSON. "
                        f"Details: {error_msg}. "
                        f"Check the 'failed_json_replies/' directory for the complete raw response. "
                        f"This may indicate: 1) LLM output was truncated, "
                        f"2) LLM returned non-JSON text, or 3) JSON structure is malformed."
                    )
                raise
            
            llm_duration_ms = int((time.time() - llm_start_time) * 1000)
            
            # Log response
            trace_logger.log_event({
                "level": "debug",
                "type": "step_end",
                "step_id": step_id,
                "step_name": "merge_step_llm",
                "task_type": "merge_step",
                "session_id": request.conversation_id,
                "user_id": request.user_id,
                "duration_ms": llm_duration_ms,
                "provider": llm_result.provider,
                "model": llm_result.model,
                "cost_usd": llm_result.cost_usd,
                "input_tokens": llm_result.input_tokens,
                "output_tokens": llm_result.output_tokens,
            })
            
            # Log response text if prompt logging is enabled
            if trace_logger.should_log_prompt():
                trace_logger.log_event({
                    "level": "debug",
                    "type": "llm_response",
                    "step_id": step_id,
                    "step_name": "merge_step_llm",
                    "task_type": "merge_step",
                    "session_id": request.conversation_id,
                    "user_id": request.user_id,
                    "response": raw_text[:1000] if raw_text else "",  # Truncate for log size
                })
            
            logger.info(
                f"merge_step LLM call successful: "
                f"provider={llm_result.provider}, "
                f"model={llm_result.model}, "
                f"cost=${llm_result.cost_usd:.4f}, "
                f"duration={llm_duration_ms}ms"
            )
            
            # Parse and convert output using adapter
            from app.services.merge_step_adapter import MergeStepAdapter
            adapter = MergeStepAdapter()
            
            # Validate output
            if not adapter.validate_merge_output(parsed_json):
                raise ValueError("Invalid merge_step output structure")
            
            # Extract dialogs from screenshot_parse bubbles
            screenshot_data = parsed_json.get("screenshot_parse", {})
            bubbles = screenshot_data.get("bubbles", [])
            
            # Convert bubbles to dialog format
            dialogs = []
            for bubble in bubbles:
                dialogs.append({
                    "speaker": bubble.get("sender", "user"),
                    "text": bubble.get("text", ""),
                    "timestamp": None,
                })
            
            logger.info(f"Extracted {len(dialogs)} dialogs from screenshot_parse bubbles")
            
            # Convert to ContextResult
            context = adapter.to_context_result(parsed_json, dialogs)
            
            # Convert to SceneAnalysisResult (without strategies yet)
            scene = adapter.to_scene_analysis_result(parsed_json)
            
            # Apply strategy selection based on recommended_scenario
            from app.services.strategy_selector import get_strategy_selector
            strategy_selector = get_strategy_selector()
            
            recommended_scenario = scene.recommended_scenario
            selected_strategies = strategy_selector.select_strategies(
                scenario=recommended_scenario,
                count=3
            )
            
            # Update scene with selected strategies
            scene.recommended_strategies = selected_strategies
            
            logger.info(
                f"Selected strategies for scenario '{recommended_scenario}': {selected_strategies}"
            )
            
            # Cache results using traditional field names for cache sharing
            await self._append_cache_event(
                request,
                "context_analysis",  # Use traditional field name
                context.model_dump(mode="json")
            )
            await self._append_cache_event(
                request,
                "scene_analysis",  # Use traditional field name
                scene.model_dump(mode="json")
            )
            
            logger.info("merge_step analysis completed and cached")
            
            return context, scene
            
        except Exception as e:
            logger.exception(f"merge_step analysis error: {e}")
            raise OrchestrationError(
                message="An error occurred during merge_step analysis",
                original_error=e,
            ) from e

    async def prepare_generate_reply(
        self,
        request: GenerateReplyRequest
    ) -> GenerateReplyResponse:
        # Check quota before starting
        if not await self.billing_service.check_quota(request.user_id):
            logger.warning(f"Quota exceeded for user {request.user_id}")
            raise QuotaExceededError(
                message=f"User {request.user_id} has exceeded their quota",
                user_id=request.user_id,
            )
        
        # Initialize execution context
        exec_ctx = ExecutionContext(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            quality=request.quality,
        )
        
        try:
            # Step 1: Build context
            cached_context = await self._get_cached_payload(request, "context_analysis")
            if cached_context:
                context = ContextResult(**cached_context)
            else:
                context = await self._execute_step(
                    exec_ctx,
                    "context_builder",
                    self._build_context,
                    request,
                )
                await self._append_cache_event(request, "context_analysis", context.model_dump(mode="json"))
            
            # Step 2: Analyze scene (传递 context 以获取当前亲密度)
            cached_scene = await self._get_cached_payload(request, "scene_analysis")
            if cached_scene:
                scene = SceneAnalysisResult(**cached_scene)
            else:
                scene = await self._execute_step(
                    exec_ctx,
                    "scene_analysis",
                    self._analyze_scene,
                    request,
                    context,  # 传递 context
                )
                await self._append_cache_event(request, "scene_analysis", scene.model_dump(mode="json"))
            
            # Step 3: Infer persona
            cached_persona = None
            if not settings.no_persona_cache:
                cached_persona = await self._get_cached_payload(request, "persona_analysis")
                
            if cached_persona:
                persona = PersonaSnapshot(**cached_persona)
            else:
                persona = await self._execute_step(
                    exec_ctx,
                    "persona_inference",
                    self._infer_persona,
                    request,
                    scene,
                )
                await self._append_cache_event(request, "persona_analysis", persona.model_dump(mode="json"))
            
            # Phase 2: Step 3.5: Plan strategies (optional, if strategy_planner available)
            strategy_plan = None
            if self.strategy_planner:
                cached_strategy = await self._get_cached_payload(request, "strategy_plan")
                if cached_strategy:
                    from app.services.strategy_planner import StrategyPlanOutput

                    strategy_plan = StrategyPlanOutput(**cached_strategy)
                else:
                    strategy_plan = await self._execute_step(
                        exec_ctx,
                        "strategy_planning",
                        self._plan_strategies,
                        context,
                        scene,
                    )
                    await self._append_cache_event(request, "strategy_plan", asdict(strategy_plan))

            # Record all billing records
            for record in exec_ctx.billing_records:
                await self.billing_service.record_call(record)

        except ContextBuildError as e:
            # Fallback for context build failure (Requirement 4.4)
            logger.error(f"Context build failed: {e}")
            return self._create_fallback_response(exec_ctx, scene=None)
            
        except Exception as e:
            # Log error and return friendly response (Requirement 4.5)
            logger.exception(f"Orchestration error: {e}")
            raise OrchestrationError(
                message="An error occurred during generation",
                original_error=e,
            ) from e

    async def generate_reply(
        self, 
        request: GenerateReplyRequest
    ) -> GenerateReplyResponse:
        """Generate a reply by orchestrating all sub-modules.
        
        Flow: Context_Builder → Scene_Analysis → Persona_Inference → 
              Reply_Generation → Intimacy_Check
        
        Args:
            request: The generation request with user/conversation info.
        
        Returns:
            GenerateReplyResponse with generated reply and metadata.
        
        Raises:
            QuotaExceededError: If user quota is exceeded.
            OrchestrationError: For other orchestration failures.
        
        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
        """
        # Check quota before starting
        if not await self.billing_service.check_quota(request.user_id):
            logger.warning(f"Quota exceeded for user {request.user_id}")
            raise QuotaExceededError(
                message=f"User {request.user_id} has exceeded their quota",
                user_id=request.user_id,
            )
        
        # Initialize execution context
        exec_ctx = ExecutionContext(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            quality=request.quality,
        )
        
        try:
            # Step 1: Build context
            cached_context = await self._get_cached_payload(request, "context_analysis")
            if cached_context:
                context = ContextResult(**cached_context)
            else:
                context = await self._execute_step(
                    exec_ctx,
                    "context_builder",
                    self._build_context,
                    request,
                )
                await self._append_cache_event(request, "context_analysis", context.model_dump(mode="json"))
            
            # Step 2: Analyze scene (传递 context 以获取当前亲密度)
            cached_scene = await self._get_cached_payload(request, "scene_analysis")
            if cached_scene:
                scene = SceneAnalysisResult(**cached_scene)
            else:
                scene = await self._execute_step(
                    exec_ctx,
                    "scene_analysis",
                    self._analyze_scene,
                    request,
                    context,  # 传递 context
                )
                await self._append_cache_event(request, "scene_analysis", scene.model_dump(mode="json"))
            
            # Step 3: Infer persona
            cached_persona = None
            if not settings.no_persona_cache:
                cached_persona = await self._get_cached_payload(request, "persona_analysis")

            if cached_persona:
                persona = PersonaSnapshot(**cached_persona)
            else:
                persona = await self._execute_step(
                    exec_ctx,
                    "persona_inference",
                    self._infer_persona,
                    request,
                    scene,
                )
                await self._append_cache_event(request, "persona_analysis", persona.model_dump(mode="json"))
            
            # Phase 2: Step 3.5: Plan strategies (optional, if strategy_planner available)
            if settings.no_strategy_planner:
                strategy_plan = None
            else:
                strategy_plan = None
                if self.strategy_planner:
                    cached_strategy = await self._get_cached_payload(request, "strategy_plan")
                    if cached_strategy:
                        from app.services.strategy_planner import StrategyPlanOutput
                        strategy_plan = StrategyPlanOutput(**cached_strategy)
                    else:
                        strategy_plan = await self._execute_step(
                            exec_ctx,
                        "strategy_planning",
                        self._plan_strategies,
                        context,
                        scene,
                    )
                    await self._append_cache_event(request, "strategy_plan", asdict(strategy_plan))
            
            # Step 4 & 5: Generate reply with intimacy check (with retries)
            cached_reply = None
            if not settings.no_reply_cache:
                cached_reply = await self._get_cached_payload(request, "reply")

            if cached_reply:
                reply_result = LLMResult(**cached_reply)
            else:
                reply_result, intimacy_result = await self._generate_with_retry(
                    exec_ctx, request, context, scene, persona, strategy_plan
                )
                if not settings.no_reply_cache:
                    await self._append_cache_event(
                        request,
                        "reply",
                        reply_result.model_dump(mode="json"),
                    )
            
            # Record all billing records
            for record in exec_ctx.billing_records:
                await self.billing_service.record_call(record)
            
            # Convert intimacy level from 0-100 scale to 1-5 scale
            intimacy_level_1_5 = self._convert_intimacy_level(scene.intimacy_level)
            
            # Build response
            return GenerateReplyResponse(
                reply_text=reply_result.text,
                confidence=persona.confidence,
                intimacy_level_before=intimacy_level_1_5,
                intimacy_level_after=intimacy_level_1_5,
                model=reply_result.model,
                provider=reply_result.provider,
                cost_usd=exec_ctx.accumulated_cost,
                fallback=False,
            )
            
        except ContextBuildError as e:
            # Fallback for context build failure (Requirement 4.4)
            logger.error(f"Context build failed: {e}")
            return self._create_fallback_response(exec_ctx, scene=None)
            
        except Exception as e:
            # Log error and return friendly response (Requirement 4.5)
            logger.exception(f"Orchestration error: {e}")
            raise OrchestrationError(
                message="An error occurred during generation",
                original_error=e,
            ) from e

    async def _execute_step(
        self,
        exec_ctx: ExecutionContext,
        step_name: str,
        step_func,
        *args,
        **kwargs,
    ):
        """Execute a single step with timing and error tracking.
        
        Args:
            exec_ctx: Execution context for tracking.
            step_name: Name of the step for logging.
            step_func: Async function to execute.
            *args, **kwargs: Arguments for the step function.
        
        Returns:
            Result from the step function.
        
        Requirements: 2.5
        """
        step_id = uuid.uuid4().hex
        trace_logger.log_event(
            {
                "level": "debug",
                "type": "step_start",
                "step_id": step_id,
                "step_name": step_name,
                "user_id": exec_ctx.user_id,
                "conversation_id": exec_ctx.conversation_id,
                "quality": exec_ctx.quality,
                "args": args,
                "kwargs": kwargs,
            }
        )

        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                step_func(*args, **kwargs),
                timeout=self.config.timeout_seconds,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            trace_logger.log_event(
                {
                    "level": "debug",
                    "type": "step_end",
                    "step_id": step_id,
                    "step_name": step_name,
                    "user_id": exec_ctx.user_id,
                    "conversation_id": exec_ctx.conversation_id,
                    "duration_ms": duration_ms,
                    "result": result,
                }
            )
            exec_ctx.step_logs.append(StepExecutionLog(
                step_name=step_name,
                status="success",
                duration_ms=duration_ms,
            ))
            return result
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            trace_logger.log_event(
                {
                    "level": "error",
                    "type": "step_error",
                    "step_id": step_id,
                    "step_name": step_name,
                    "user_id": exec_ctx.user_id,
                    "conversation_id": exec_ctx.conversation_id,
                    "duration_ms": duration_ms,
                    "error": "timeout",
                }
            )
            exec_ctx.step_logs.append(StepExecutionLog(
                step_name=step_name,
                status="failed",
                duration_ms=duration_ms,
                error="timeout",
            ))
            raise
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            trace_logger.log_event(
                {
                    "level": "error",
                    "type": "step_error",
                    "step_id": step_id,
                    "step_name": step_name,
                    "user_id": exec_ctx.user_id,
                    "conversation_id": exec_ctx.conversation_id,
                    "duration_ms": duration_ms,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
            exec_ctx.step_logs.append(StepExecutionLog(
                step_name=step_name,
                status="failed",
                duration_ms=duration_ms,
                error=str(e),
            ))
            raise

    async def _build_context(
        self,
        request: GenerateReplyRequest,
    ) -> ContextResult:
        """Build context from request.
        
        Args:
            request: The generation request.
        
        Returns:
            ContextResult from context builder.
        
        Raises:
            ContextBuildError: If context building fails.
        """
        try:
            messages = self._dialogs_to_messages(request.dialogs)
            input_data = ContextBuilderInput(
                user_id=request.user_id,
                target_id=request.target_id,
                conversation_id=request.conversation_id,
                history_dialog=messages,
                emotion_trend=None,
            )
            result = await self.context_builder.build_context(input_data)

            if self.persistence_service is not None and result.conversation_summary:
                await self.persistence_service.save_conversation_summary(
                    user_id=request.user_id,
                    target_id=request.target_id,
                    conversation_id=request.conversation_id,
                    summary=result.conversation_summary,
                )

            history_conversation = "no history conversation"
            if self.persistence_service is not None:
                try:
                    logs = await self.persistence_service.list_conversation_summaries(
                        user_id=request.user_id,
                        target_id=request.target_id,
                        limit=20,
                        offset=0,
                    )
                    summaries: list[str] = []
                    for log in logs:
                        if getattr(log, "conversation_id", None) == request.conversation_id:
                            continue
                        summary = getattr(log, "summary", "")
                        if isinstance(summary, str) and summary.strip():
                            summaries.append(summary.strip())
                    if summaries:
                        history_conversation = "\n".join(summaries)
                except Exception:
                    history_conversation = "no history conversation"
            result.history_conversation = history_conversation

            return result
        except Exception as e:
            raise ContextBuildError(
                message=f"Failed to build context: {e}",
                conversation_id=request.conversation_id,
            ) from e

    async def _analyze_scene(
        self, 
        request: GenerateReplyRequest,
        context: ContextResult,
    ) -> SceneAnalysisResult:
        """Analyze conversation scene.
        
        Args:
            request: The generation request.
            context: Context result with current intimacy level.
        
        Returns:
            SceneAnalysisResult from scene analyzer.
        """
        input_data = SceneAnalysisInput(
            conversation_id=request.conversation_id,
            history_dialog=self._dialogs_to_messages(request.dialogs),
            emotion_trend=None,
            current_conversation_summary=context.conversation_summary or "",
            intimacy_value=request.intimacy_value,  # 用户设置的亲密度
            current_intimacy_level=context.current_intimacy_level,  # 当前分析的亲密度
        )
        return await self.scene_analyzer.analyze_scene(input_data)

    async def _infer_persona(
        self,
        request: GenerateReplyRequest,
        scene: SceneAnalysisResult,
    ) -> PersonaSnapshot:
        """Infer user persona.
        
        Args:
            request: The generation request.
            scene: Scene analysis result.
        
        Returns:
            PersonaSnapshot from persona inferencer.
        """
        input_data = PersonaInferenceInput(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            scene=scene.recommended_scenario,  # 使用推荐场景
            history_dialog=self._dialogs_to_messages(request.dialogs),
            persona=request.persona,  # 用户提供的persona
            intimacy=request.intimacy_value,  # 用户设置的亲密度
            relationship_state=scene.relationship_state,
        )
        return await self.persona_inferencer.infer_persona(input_data)
    
    async def _plan_strategies(
        self,
        context: ContextResult,
        scene: SceneAnalysisResult,
    ):
        """Plan conversation strategies (Phase 2 optimization).
        
        Args:
            context: Context result with conversation summary
            scene: Scene analysis result
        
        Returns:
            Strategy plan output
        """
        from app.services.strategy_planner import StrategyPlanInput
        
        input_data = StrategyPlanInput(
            scene=scene,
            conversation_summary=context.conversation_summary or "",
            intimacy_level=scene.intimacy_level,
            current_intimacy_level=context.current_intimacy_level
        )
        return await self.strategy_planner.plan_strategies(input_data)

    async def _generate_with_retry(
        self,
        exec_ctx: ExecutionContext,
        request: GenerateReplyRequest,
        context: ContextResult,
        scene: SceneAnalysisResult,
        persona: PersonaSnapshot,
        strategy_plan=None,
    ):
        """Generate reply with retry logic for intimacy check failures.
        
        Implements retry up to max_retries times when intimacy check fails.
        Falls back to conservative reply after exhausting retries.
        
        Args:
            exec_ctx: Execution context for tracking.
            request: The generation request.
            context: Built context.
            scene: Scene analysis result.
            persona: Inferred persona.
            strategy_plan: Optional strategy plan from Phase 2.
        
        Returns:
            Tuple of (LLMResult, IntimacyCheckResult).
        
        Requirements: 2.3, 2.4, 4.2
        """
        quality = self._get_effective_quality(exec_ctx, request.quality)
        
        # Force premium quality for reply generation
        # Override to use more expensive/better models
        quality = "premium"  # Use premium quality models for better replies
        logger.info(f"Using premium quality model for reply generation")
        
        last_reply_result = None
        last_intimacy_result = None

        if self.cache_service is not None:
            try:
                timeline = await self.cache_service.get_timeline(
                    session_id=request.conversation_id,
                    category="context_analysis",
                    scene=request.scene,
                )
                payloads = [event.get("payload") for event in timeline if isinstance(event, dict)]
                contexts = [ContextResult(**payload) for payload in payloads if isinstance(payload, dict)]

                if contexts:
                    summary_parts: list[str] = []
                    seen_summaries: set[str] = set()
                    risk_flags: list[str] = []
                    seen_flags: set[str] = set()
                    conversation: list[Message] = []
                    history_parts: list[str] = []

                    for ctx in contexts:
                        if isinstance(ctx.conversation_summary, str) and ctx.conversation_summary and ctx.conversation_summary not in seen_summaries:
                            summary_parts.append(ctx.conversation_summary)
                            seen_summaries.add(ctx.conversation_summary)

                        for flag in (ctx.risk_flags or []):
                            if flag not in seen_flags:
                                risk_flags.append(flag)
                                seen_flags.add(flag)

                        if isinstance(ctx.history_conversation, str) and ctx.history_conversation:
                            history_parts.append(ctx.history_conversation)

                    latest = contexts[-1]
                    history_context = ContextResult(
                        conversation_summary="\n".join(summary_parts) if summary_parts else latest.conversation_summary,
                        emotion_state=next((c.emotion_state for c in reversed(contexts) if isinstance(c.emotion_state, str) and c.emotion_state), latest.emotion_state),
                        current_intimacy_level=latest.current_intimacy_level,
                        risk_flags=risk_flags,
                        conversation=context.conversation,
                        history_conversation="\n".join(history_parts),
                    )
                    context = history_context
            except Exception as exc:
                logger.warning("Failed to aggregate cached context for session %s: %s", request.conversation_id, exc)

        
        for attempt in range(self.config.max_retries):
            try:
                # Generate reply
                reply_input = ReplyGenerationInput(
                    user_id=request.user_id,
                    prompt=f"Generate a reply for conversation {request.conversation_id}",
                    quality=quality,
                    context=context,
                    scene=scene,
                    persona=persona,
                    language=request.language,  # 传递语言参数
                )
                reply_result = await self._execute_step(
                    exec_ctx,
                    f"reply_generation_attempt_{attempt + 1}",
                    self.reply_generator.generate_reply,
                    reply_input,
                )
                last_reply_result = reply_result
                
                # Track cost
                self._track_cost(exec_ctx, reply_result, "generation")
                
                # Check if cost limit exceeded, force cheap quality
                if exec_ctx.accumulated_cost >= self.billing_config.cost_limit_usd:
                    exec_ctx.forced_cheap = True
                    quality = "cheap"
                    logger.info(f"Cost limit reached, forcing cheap quality")
                
                # Skip intimacy check if disabled in settings
                if settings.no_intimacy_check:
                    logger.info("Intimacy check disabled by configuration")
                    # Create a passing intimacy result
                    from app.models.schemas import IntimacyCheckResult
                    intimacy_result = IntimacyCheckResult(
                        passed=True,
                        reason="Intimacy check disabled",
                        score=1.0,
                    )
                    return reply_result, intimacy_result
                
                # Check intimacy
                intimacy_input = IntimacyCheckInput(
                    reply_text=reply_result.text,
                    intimacy_level=scene.intimacy_level,
                    persona=persona,
                )
                
                intimacy_result = await self._execute_step(
                    exec_ctx,
                    f"intimacy_check_attempt_{attempt + 1}",
                    self.intimacy_checker.check,
                    intimacy_input,
                )
                last_intimacy_result = intimacy_result
                
                if intimacy_result.passed:
                    return reply_result, intimacy_result
                
                logger.info(
                    f"Intimacy check failed (attempt {attempt + 1}): "
                    f"{intimacy_result.reason}"
                )
                
            except asyncio.TimeoutError:
                # On timeout, switch to fallback model (Requirement 4.1)
                logger.warning(f"Timeout on attempt {attempt + 1}, using fallback model")
                quality = "cheap"
                exec_ctx.forced_cheap = True
                continue
        
        # Exhausted retries, return fallback (Requirement 2.4, 4.2)
        logger.warning(f"Exhausted {self.config.max_retries} retries, using fallback")
        
        if last_reply_result:
            # Return last generated reply even if intimacy check failed
            return last_reply_result, last_intimacy_result
        
        # No successful generation, create fallback using FallbackStrategy
        fallback_reply = FallbackStrategy.create_fallback_llm_result(
            scene=scene.scene,
            context=context,
        )
        fallback_intimacy = FallbackStrategy.create_fallback_intimacy_result()
        return fallback_reply, fallback_intimacy

    def _get_effective_quality(
        self,
        exec_ctx: ExecutionContext,
        requested_quality: Literal["cheap", "normal", "premium"],
    ) -> Literal["cheap", "normal", "premium"]:
        """Get effective quality considering cost limits.
        
        Args:
            exec_ctx: Execution context.
            requested_quality: Originally requested quality.
        
        Returns:
            Effective quality to use.
        
        Requirements: 4.3
        """
        if exec_ctx.forced_cheap:
            return "cheap"
        if exec_ctx.accumulated_cost >= self.billing_config.cost_limit_usd:
            exec_ctx.forced_cheap = True
            return "cheap"
        return requested_quality

    def _track_cost(
        self,
        exec_ctx: ExecutionContext,
        result,
        task_type: Literal["scene", "persona", "generation", "qc"],
    ) -> None:
        """Track cost from an LLM result.
        
        Args:
            exec_ctx: Execution context.
            result: LLM result with cost info.
            task_type: Type of task for billing record.
        """
        exec_ctx.accumulated_cost += result.cost_usd
        
        record = LLMCallRecord(
            user_id=exec_ctx.user_id,
            task_type=task_type,
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
            latency_ms=0,  # Will be updated from step logs
            created_at=datetime.utcnow(),
        )
        exec_ctx.billing_records.append(record)

    def _convert_intimacy_level(self, intimacy_level_0_100: int) -> int:
        """Convert intimacy level from 0-100 scale to 1-5 scale.
        
        Args:
            intimacy_level_0_100: Intimacy level on 0-100 scale
        
        Returns:
            Intimacy level on 1-5 scale
        """
        # Map 0-100 to 1-5
        # 0-20 -> 1, 21-40 -> 2, 41-60 -> 3, 61-80 -> 4, 81-100 -> 5
        if intimacy_level_0_100 <= 20:
            return 1
        elif intimacy_level_0_100 <= 40:
            return 2
        elif intimacy_level_0_100 <= 60:
            return 3
        elif intimacy_level_0_100 <= 80:
            return 4
        else:
            return 5

    def _create_fallback_response(
        self,
        exec_ctx: ExecutionContext,
        scene: SceneAnalysisResult | None,
        context: ContextResult | None = None,
    ) -> GenerateReplyResponse:
        """Create a fallback response for error scenarios.
        
        Args:
            exec_ctx: Execution context.
            scene: Scene analysis result if available.
            context: Context result if available.
        
        Returns:
            GenerateReplyResponse with fallback content.
        
        Requirements: 4.4
        """
        scene_type = scene.scenario if scene else None
        intimacy_level = self._convert_intimacy_level(scene.intimacy_level) if scene else 3
        
        # Use FallbackStrategy for consistent fallback behavior
        fallback_text = FallbackStrategy.get_fallback_for_retry_exhaustion(
            scene=scene,
            context=context,
        )
        
        return GenerateReplyResponse(
            reply_text=fallback_text,
            confidence=0.5,
            intimacy_level_before=intimacy_level,
            intimacy_level_after=intimacy_level,
            model="template",
            provider="fallback",
            cost_usd=exec_ctx.accumulated_cost,
            fallback=True,
        )

    def _create_fallback_scene_analysis(self) -> SceneAnalysisResult:
        """Create a fallback SceneAnalysisResult for error scenarios.
        
        Returns:
            SceneAnalysisResult with default/safe values.
        """
        return SceneAnalysisResult(
            scenario="safe",
            intimacy_level=50,  # Neutral intimacy level
            relationship_state="维持",  # "maintain" - safe default
            current_scenario="safe",
            recommended_scenario="safe",
            recommended_strategies=["BE_SUPPORTIVE", "SHOW_INTEREST", "BE_RESPECTFUL"],
            risk_flags=[],
        )

    def _messages_to_dialogs(self, messages):
        return None

    def _dialogs_to_messages(self, dialogs):
        messages = []
        for i, dialog in enumerate(dialogs):
            messages.append(Message(
                id = str(i),
                speaker = dialog['speaker'],
                content = dialog['text'],
                timestamp = dialog.get("timestamp", None)
            ))
        return messages

    async def _get_cached_payload(self, request: GenerateReplyRequest, category: str) -> dict | None:
        # Skip cache if:
        # 1. No cache service
        # 2. No resource identifier (neither resource nor resources)
        # 3. Force regenerate flag is set
        if self.cache_service is None or (not request.resource and not request.resources) or request.force_regenerate:
            return None
        try:
            # Use first resource from resources list if resource is not set
            resource_key = request.resource or (request.resources[0] if request.resources else None)
            if not resource_key:
                return None
                
            cached_event = await self.cache_service.get_resource_category_last(
                session_id=request.conversation_id,
                category=category,
                resource=resource_key,
                scene=request.scene,
            )
            if cached_event:
                payload = cached_event.get("payload")
                if isinstance(payload, dict):
                    logger.info(f"Cache hit for category={category}, resource={resource_key}")
                    return payload
        except Exception as exc:
            logger.warning("Cache read failed for category=%s: %s", category, exc)
        return None

    async def _append_cache_event(self, request: GenerateReplyRequest, category: str, payload: dict) -> None:
        if self.cache_service is None or (not request.resource and not request.resources):
            return
        try:
            resources = []
            if request.resources:
                resources.extend(request.resources)
            if request.resource:
                resources.append(request.resource)

            for r in set(resources):
                await self.cache_service.append_event(
                    session_id=request.conversation_id,
                    category=category,
                    resource=r,
                    payload=payload,
                    scene=request.scene,
                )
        except Exception as exc:
            logger.warning("Cache append failed for category=%s: %s", category, exc)