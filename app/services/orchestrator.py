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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.core.config import OrchestratorConfig as OrchestratorConfigSettings
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
        config: OrchestratorConfig | None = None,
        billing_config: BillingConfig | None = None,
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
            config: Orchestrator configuration (retry, timeout settings).
            billing_config: Billing configuration (cost limits).
        """
        self.context_builder = context_builder
        self.scene_analyzer = scene_analyzer
        self.persona_inferencer = persona_inferencer
        self.reply_generator = reply_generator
        self.intimacy_checker = intimacy_checker
        self.billing_service = billing_service
        self.persistence_service = persistence_service
        self.config = config or OrchestratorConfig()
        self.billing_config = billing_config or BillingConfig()

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
            context = await self._execute_step(
                exec_ctx,
                "context_builder",
                self._build_context,
                request,
            )
            print(type(context), type(self.context_builder))
            print("step 1:", context)
            
            # Step 2: Analyze scene (传递 context 以获取当前亲密度)
            scene = await self._execute_step(
                exec_ctx,
                "scene_analysis",
                self._analyze_scene,
                request,
                context,  # 传递 context
            )
            print(type(scene), type(self.scene_analyzer))
            print("step 2:", scene)
            
            # Step 3: Infer persona
            persona = await self._execute_step(
                exec_ctx,
                "persona_inference",
                self._infer_persona,
                request,
                scene,
            )
            print(type(persona), type(self.persona_inferencer))
            print("step 3:", persona)
            # Step 4 & 5: Generate reply with intimacy check (with retries)
            reply_result, intimacy_result = await self._generate_with_retry(
                exec_ctx, request, context, scene, persona
            )
            print("reply_result", reply_result)
            # Record all billing records
            for record in exec_ctx.billing_records:
                await self.billing_service.record_call(record)
            
            # Convert intimacy level from 0-101 scale to 1-5 scale
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
            print(traceback.format_exc())
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
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                step_func(*args, **kwargs),
                timeout=self.config.timeout_seconds,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            exec_ctx.step_logs.append(StepExecutionLog(
                step_name=step_name,
                status="success",
                duration_ms=duration_ms,
            ))
            return result
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            exec_ctx.step_logs.append(StepExecutionLog(
                step_name=step_name,
                status="failed",
                duration_ms=duration_ms,
                error="timeout",
            ))
            raise
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            exec_ctx.step_logs.append(StepExecutionLog(
                step_name=step_name,
                status="failed",
                duration_ms=duration_ms,
                error=str(e),
            ))
            raise

    async def _build_context(
        self, 
        request: GenerateReplyRequest
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
            print("start to build input data")
            input_data = ContextBuilderInput(
                user_id=request.user_id,
                target_id=request.target_id,
                conversation_id=request.conversation_id,
                history_dialog=messages,
                emotion_trend=None,
            )
            print("_build_context", request.dialogs, type(self.context_builder))
            result = await self.context_builder.build_context(input_data)

            if self.persistence_service is not None and result.conversation_summary:
                await self.persistence_service.save_conversation_summary(
                    user_id=request.user_id,
                    target_id=request.target_id,
                    conversation_id=request.conversation_id,
                    summary=result.conversation_summary,
                )

            return result
        except Exception as e:
            
            print(traceback.format_exc())
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
        messages = self._dialogs_to_messages(request.dialogs)
        input_data = SceneAnalysisInput(
            conversation_id=request.conversation_id,
            history_dialog=messages,
            emotion_trend=None,
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
        )
        return await self.persona_inferencer.infer_persona(input_data)

    async def _generate_with_retry(
        self,
        exec_ctx: ExecutionContext,
        request: GenerateReplyRequest,
        context: ContextResult,
        scene: SceneAnalysisResult,
        persona: PersonaSnapshot,
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
        
        Returns:
            Tuple of (LLMResult, IntimacyCheckResult).
        
        Requirements: 2.3, 2.4, 4.2
        """
        quality = self._get_effective_quality(exec_ctx, request.quality)
        last_reply_result = None
        last_intimacy_result = None
        
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
                print('reply_generator', type(self.reply_generator))
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

    def _convert_intimacy_level(self, intimacy_level_0_101: int) -> int:
        """Convert intimacy level from 0-101 scale to 1-5 scale.
        
        Args:
            intimacy_level_0_101: Intimacy level on 0-101 scale
        
        Returns:
            Intimacy level on 1-5 scale
        """
        # Map 0-101 to 1-5
        # 0-20 -> 1, 21-40 -> 2, 41-60 -> 3, 61-80 -> 4, 81-101 -> 5
        if intimacy_level_0_101 <= 20:
            return 1
        elif intimacy_level_0_101 <= 40:
            return 2
        elif intimacy_level_0_101 <= 60:
            return 3
        elif intimacy_level_0_101 <= 80:
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