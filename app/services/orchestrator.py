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
        
        # Background task management
        self._background_tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

    def _log_merge_step_extraction(
        self,
        session_id: str,
        strategy: str,
        model: str,
        parsed_json: dict
    ) -> None:
        """Log extracted conversation details from merge_step analysis.
        
        Args:
            session_id: Session ID for logging
            strategy: Strategy name (multimodal/premium)
            model: Model name
            parsed_json: Parsed merge_step JSON response
        """
        # Check if logging is enabled
        from app.core.config import settings
        if not settings.debug_config.log_merge_step_extraction:
            return
        
        try:
            # Extract bubbles from screenshot_parse section
            screenshot_parse = parsed_json.get("screenshot_parse", {})
            bubbles = screenshot_parse.get("bubbles", [])
            participants = screenshot_parse.get("participants", {})
            
            # Log participants info
            self_info = participants.get("self", {})
            other_info = participants.get("other", {})
            user_nickname = self_info.get("nickname", "Unknown")
            target_nickname = other_info.get("nickname", "Unknown")
            
            logger.info(
                f"[{session_id}] merge_step [{strategy}|{model}] Participants: "
                f"User='{user_nickname}', Target='{target_nickname}'"
            )
            
            # Sort bubbles by y-coordinate (top to bottom)
            sorted_bubbles = sorted(bubbles, key=lambda b: b.get("bbox", {}).get("y1", 0))
            
            # Get layout info to understand role mapping
            layout = screenshot_parse.get("layout", {})
            left_role = layout.get("left_role", "unknown")
            right_role = layout.get("right_role", "unknown")
            
            # Log bubble details with layout context
            logger.info(
                f"[{session_id}] FINAL [{strategy}|{model}] Layout: left={left_role}, right={right_role}"
            )
            logger.info(
                f"[{session_id}] FINAL [{strategy}|{model}] Extracted {len(sorted_bubbles)} bubbles (sorted top->bottom):"
            )
            
            for idx, bubble in enumerate(sorted_bubbles, 1):
                sender = bubble.get("sender", "unknown")
                text = bubble.get("text", "")
                logger.info(f"[{__name__}:_log_merge_step_extraction:L{195}] Original bubble text before truncation: {text}")
                column = bubble.get("column", "unknown")
                bbox = bubble.get("bbox", {})
                x1 = bbox.get("x1", 0)
                y1 = bbox.get("y1", 0)
                x2 = bbox.get("x2", 0)
                y2 = bbox.get("y2", 0)
                
                # Show expected role based on layout
                expected_role = left_role if column == "left" else right_role
                role_match = "OK" if sender == expected_role else "MISMATCH"
                
                # Truncate long messages for readability (keep emoji in content)
                display_text = text[:100] + "..." if len(text) > 100 else text
                
                logger.info(
                    f"[{session_id}]   [{idx}] {sender}({column}) {role_match} "
                    f"bbox=[{x1},{y1},{x2},{y2}]: {display_text}"
                )
                
        except Exception as e:
            logger.warning(f"[{session_id}] Failed to log merge_step extraction: {e}", exc_info=True)

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
    ) -> tuple[ContextResult, SceneAnalysisResult, dict]:
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
            Tuple of (ContextResult, SceneAnalysisResult, parsed_json)
            The parsed_json contains the raw merge_step output including bbox coordinates
            
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
            logger.info(f"[{request.conversation_id}] merge_step_analysis: force_regenerate={request.force_regenerate}, resource={request.resource}, resources={request.resources}, scene={request.scene}")
            
            if request.force_regenerate:
                logger.info(f"[{request.conversation_id}] Skipping cache due to force_regenerate=True")
            
            cached_context = await self._get_cached_payload(request, "context_analysis")
            cached_scene = await self._get_cached_payload(request, "scene_analysis")
            cached_screenshot_parse = await self._get_cached_payload(request, "screenshot_parse")
            
            # Also try to read from image_result for backward compatibility with non-merge_step
            if not cached_screenshot_parse:
                cached_image_result = await self._get_cached_payload(request, "image_result")
                if cached_image_result:
                    logger.info(f"[{request.conversation_id}] Found image_result cache, converting to screenshot_parse format")
                    # Convert ImageResult format to screenshot_parse format
                    dialogs = cached_image_result.get("dialogs", [])
                    bubbles = []
                    for dialog in dialogs:
                        position = dialog.get("position", [0, 0, 0, 0])
                        bubbles.append({
                            "sender": dialog.get("speaker", "user"),
                            "text": dialog.get("text", ""),
                            "bbox": {
                                "x1": position[0] if len(position) > 0 else 0,
                                "y1": position[1] if len(position) > 1 else 0,
                                "x2": position[2] if len(position) > 2 else 0,
                                "y2": position[3] if len(position) > 3 else 0,
                            }
                        })
                    cached_screenshot_parse = {
                        "screenshot_parse": {
                            "bubbles": bubbles
                        }
                    }
            
            if cached_context and cached_scene:
                if settings.debug.log_cache_operations:
                    logger.error(f"[{request.conversation_id}] ===== CACHE READ DEBUG =====")
                    logger.error(f"[{request.conversation_id}] Using cached merge_step results: session_id={request.conversation_id}, resource={request.resource}, resources={request.resources}, scene={request.scene}")
                    logger.error(f"[{request.conversation_id}] Cached strategy={cached_context.get('_strategy')}, model={cached_context.get('_model')}")
                    logger.error(f"[{request.conversation_id}] ===== END CACHE READ DEBUG =====")
                context = ContextResult(**cached_context)
                scene = SceneAnalysisResult(**cached_scene)
                
                # Log cached conversation details
                # Extract model info from cache metadata if available
                cached_model = cached_context.get("_model", "unknown")
                cached_strategy = cached_context.get("_strategy", "unknown")
                
                logger.info(
                    f"[{request.conversation_id}] merge_step [CACHED|{cached_strategy}|{cached_model}] "
                    f"Conversation: {len(context.conversation)} messages"
                )
                for idx, msg in enumerate(context.conversation, 1):
                    display_content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                    logger.info(
                        f"[{request.conversation_id}]   [{idx}] {msg.speaker}: {display_content}"
                    )
                
                # Reconstruct parsed_json with screenshot_parse for bbox information
                cached_parsed_json = {
                    "screenshot_parse": cached_screenshot_parse.get("screenshot_parse", {}) if cached_screenshot_parse else {},
                    "conversation_analysis": {},  # Not needed for bbox reconstruction
                    "scenario_decision": {},  # Not needed for bbox reconstruction
                }
                
                return context, scene, cached_parsed_json  # Return reconstructed parsed_json
            
            # No cache, perform merge_step analysis
            logger.info("Performing merge_step analysis with LLM")
            
            # Get merge_step prompt (use active version)
            from app.services.prompt_manager import get_prompt_manager, PromptType
            pm = get_prompt_manager()
            prompt = pm.get_active_prompt(PromptType.MERGE_STEP)
            
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
                winning_strategy, llm_result, premium_result_or_task = await temp_parser._race_multimodal_calls(
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
                    
                    logger.info(f"[{__name__}:analyze_with_merge_step:L{453}] LLM raw response length: {len(llm_result.text)}")
                    logger.info(f"[{__name__}:analyze_with_merge_step:L{454}] LLM parsed_json bubbles count: {len(parsed_json.get('screenshot_parse', {}).get('bubbles', []))}")
                    
                    # Log first bubble text to verify LLM output
                    bubbles_check = parsed_json.get('screenshot_parse', {}).get('bubbles', [])
                    if bubbles_check:
                        first_bubble_text = bubbles_check[0].get('text', '')
                        logger.info(f"[{__name__}:analyze_with_merge_step:L{458}] First bubble text from LLM (length={len(first_bubble_text)}): {first_bubble_text[:200]}...")
                    
                    logger.info(f"About to call _log_merge_step_extraction for session {request.conversation_id}")
                    
                    # Log extracted conversation details
                    self._log_merge_step_extraction(
                        session_id=request.conversation_id,
                        strategy=winning_strategy,
                        model=llm_result.model,
                        parsed_json=parsed_json
                    )
                    
                    logger.info(f"Finished calling _log_merge_step_extraction")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from merge_step: {e}")
                    raise RuntimeError(f"Failed to parse JSON: {str(e)}")
                
                # Handle premium result caching in background
                # premium_result_or_task could be:
                # 1. A result object (if premium completed)
                # 2. A task object (if premium is still running)
                import asyncio
                if isinstance(premium_result_or_task, asyncio.Task):
                    # Premium is still running, schedule background caching
                    logger.info(f"[{request.conversation_id}] Premium task still running, will cache in background")
                    
                    # Extract necessary info from request before it becomes invalid
                    # Collect all resources to cache (same logic as _append_cache_event)
                    resources = []
                    if request.resources:
                        resources.extend(request.resources)
                    if request.resource:
                        resources.append(request.resource)
                    
                    conversation_id = request.conversation_id
                    scene_id = request.scene if hasattr(request, 'scene') else ""  # Rename to scene_id to avoid confusion
                    cache_service = self.cache_service  # Use instance variable instead of get_cache_service()
                    
                    # Debug: Log the captured scene value
                    if settings.debug.log_cache_operations:
                        logger.error(f"[{conversation_id}] ===== SCENE CAPTURE DEBUG =====")
                        logger.error(f"[{conversation_id}] Captured scene_id value: '{scene_id}' (type: {type(scene_id).__name__})")
                        logger.error(f"[{conversation_id}] ===== END SCENE CAPTURE DEBUG =====")
                    
                    async def cache_premium_when_ready():
                        try:
                            # Add timeout protection (default: 30 seconds)
                            timeout = getattr(settings.llm, 'premium_cache_timeout', 30.0)
                            premium_result_tuple = await asyncio.wait_for(
                                premium_result_or_task,
                                timeout=timeout
                            )
                            # premium_result_tuple is ("premium", result) or ("premium", None)
                            if premium_result_tuple and len(premium_result_tuple) == 2:
                                _, premium_result = premium_result_tuple
                            else:
                                premium_result = None
                                
                            if premium_result:
                                logger.info(f"[{conversation_id}] Background: Premium task completed, processing result")
                                premium_parsed = parse_json_with_markdown(premium_result.text)
                                if validate_merge_step_result(premium_parsed):
                                    logger.info(f"[{conversation_id}] Background: Premium result is valid")
                                    
                                    # Extract dialogs from screenshot_parse bubbles
                                    screenshot_data = premium_parsed.get("screenshot_parse", {})
                                    bubbles = screenshot_data.get("bubbles", [])
                                    
                                    # Convert bubbles to dialog format
                                    dialogs = []
                                    for bubble in bubbles:
                                        dialogs.append({
                                            "speaker": bubble.get("sender", "user"),
                                            "text": bubble.get("text", ""),
                                            "timestamp": None,
                                        })
                                    
                                    # Convert to ContextResult and SceneAnalysisResult
                                    premium_context = merge_adapter.to_context_result(premium_parsed, dialogs)
                                    premium_scene = merge_adapter.to_scene_analysis_result(premium_parsed)
                                    
                                    # Log premium extraction details (same as multimodal)
                                    logger.info(f"[{conversation_id}] Background: Logging premium extraction details")
                                    self._log_merge_step_extraction(
                                        session_id=conversation_id,
                                        strategy="premium",
                                        model=premium_result.model,
                                        parsed_json=premium_parsed
                                    )
                                    
                                    # Add metadata for cache logging
                                    premium_context_data = premium_context.model_dump()
                                    premium_context_data["_model"] = premium_result.model
                                    premium_context_data["_strategy"] = "premium"
                                    
                                    premium_scene_data = premium_scene.model_dump()
                                    premium_scene_data["_model"] = premium_result.model
                                    premium_scene_data["_strategy"] = "premium"
                                    
                                    # Cache to all resources (same logic as _append_cache_event)
                                    if cache_service and resources:
                                        if settings.debug.log_cache_operations:
                                            logger.error(f"[{conversation_id}] ===== PREMIUM CACHE WRITE DEBUG =====")
                                            logger.error(f"[{conversation_id}] Background: Caching premium results to {len(resources)} resource(s): {resources}")
                                            logger.error(f"[{conversation_id}] Premium strategy=premium, model={premium_result.model}")
                                            logger.error(f"[{conversation_id}] ===== END PREMIUM CACHE WRITE DEBUG =====")
                                        
                                        # Cache screenshot_parse separately for bbox information
                                        premium_screenshot_parse_data = {
                                            "screenshot_parse": premium_parsed.get("screenshot_parse", {}),
                                            "_model": premium_result.model,
                                            "_strategy": "premium",
                                        }
                                        
                                        for resource in set(resources):
                                            # Cache screenshot_parse
                                            if settings.debug.log_cache_operations:
                                                logger.error(f"[{conversation_id}] ===== PREMIUM CACHE SCENE DEBUG =====")
                                                logger.error(f"[{conversation_id}] About to cache with scene_id='{scene_id}' (type: {type(scene_id).__name__})")
                                                logger.error(f"[{conversation_id}] ===== END PREMIUM CACHE SCENE DEBUG =====")
                                            logger.info(f"[{conversation_id}] Background: Caching premium screenshot_parse: session_id={conversation_id}, resource={resource}, scene={scene_id}")
                                            await cache_service.append_event(
                                                session_id=conversation_id,
                                                category="screenshot_parse",
                                                resource=resource,
                                                payload=premium_screenshot_parse_data,
                                                scene=scene_id
                                            )
                                            
                                            # Also cache in image_result format for backward compatibility
                                            screenshot_data = premium_parsed.get("screenshot_parse", {})
                                            bubbles = screenshot_data.get("bubbles", [])
                                            dialogs_for_image_result = []
                                            for bubble in bubbles:
                                                bbox = bubble.get("bbox", {})
                                                dialog_item = {
                                                    "position": [
                                                        bbox.get("x1", 0),
                                                        bbox.get("y1", 0),
                                                        bbox.get("x2", 0),
                                                        bbox.get("y2", 0),
                                                    ],
                                                    "text": bubble.get("text", ""),
                                                    "speaker": bubble.get("sender", "user"),
                                                    "from_user": (bubble.get("sender", "user") == "user"),
                                                }
                                                dialogs_for_image_result.append(dialog_item)
                                            
                                            premium_image_result_data = {
                                                "content": resource,
                                                "dialogs": dialogs_for_image_result,
                                                "scenario": premium_scene.recommended_scenario,
                                                "_model": premium_result.model,
                                                "_strategy": "premium",
                                            }
                                            logger.info(f"[{conversation_id}] Background: Caching premium image_result: session_id={conversation_id}, resource={resource}, scene={scene_id}")
                                            await cache_service.append_event(
                                                session_id=conversation_id,
                                                category="image_result",
                                                resource=resource,
                                                payload=premium_image_result_data,
                                                scene=scene_id
                                            )
                                            
                                            # Cache context_analysis
                                            logger.info(f"[{conversation_id}] Background: Caching premium context_analysis: session_id={conversation_id}, resource={resource}, scene={scene_id}")
                                            await cache_service.append_event(
                                                session_id=conversation_id,
                                                category="context_analysis",
                                                resource=resource,
                                                payload=premium_context_data,
                                                scene=scene_id
                                            )
                                            
                                            # Cache scene_analysis
                                            logger.info(f"[{conversation_id}] Background: Caching premium scene_analysis: session_id={conversation_id}, resource={resource}, scene={scene_id}")
                                            await cache_service.append_event(
                                                session_id=conversation_id,
                                                category="scene_analysis",
                                                resource=resource,
                                                payload=premium_scene_data,
                                                scene=scene_id
                                            )
                                    
                                    logger.info(f"[{conversation_id}] Background: Premium result cached successfully")
                                else:
                                    logger.warning(f"[{conversation_id}] Background: Premium result invalid, not caching")
                            else:
                                logger.warning(f"[{conversation_id}] Background: Premium result is None")
                        except asyncio.TimeoutError:
                            logger.warning(f"[{conversation_id}] Background: Premium task timeout after {timeout}s")
                        except asyncio.CancelledError:
                            logger.info(f"[{conversation_id}] Background: Premium caching cancelled")
                        except Exception as e:
                            logger.warning(f"[{conversation_id}] Background: Failed to cache premium result: {e}")
                            import traceback
                            logger.debug(f"[{conversation_id}] Background: Traceback: {traceback.format_exc()}")
                    
                    # Start background task with tracking
                    background_task = asyncio.create_task(cache_premium_when_ready())
                    logger.info(f"[{request.conversation_id}] Started background task for premium caching: task_id={id(background_task)}")
                    self._register_background_task(
                        background_task, 
                        f"premium_cache_{conversation_id[:8]}"
                    )
                    
                elif premium_result_or_task and premium_result_or_task != llm_result:
                    # Premium completed and is different from winning result
                    try:
                        premium_parsed = parse_json_with_markdown(premium_result_or_task.text)
                        if validate_merge_step_result(premium_parsed):
                            logger.info(f"[{request.conversation_id}] Caching premium result for future use")
                            
                            # Extract dialogs from screenshot_parse bubbles
                            screenshot_data = premium_parsed.get("screenshot_parse", {})
                            bubbles = screenshot_data.get("bubbles", [])
                            
                            # Convert bubbles to dialog format
                            dialogs = []
                            for bubble in bubbles:
                                dialogs.append({
                                    "speaker": bubble.get("sender", "user"),
                                    "text": bubble.get("text", ""),
                                    "timestamp": None,
                                })
                            
                            # Convert to ContextResult and SceneAnalysisResult
                            premium_context = merge_adapter.to_context_result(premium_parsed, dialogs)
                            premium_scene = merge_adapter.to_scene_analysis_result(premium_parsed)
                            
                            # Add metadata for cache logging
                            premium_context_data = premium_context.model_dump()
                            premium_context_data["_model"] = premium_result_or_task.model
                            premium_context_data["_strategy"] = "premium"
                            
                            premium_scene_data = premium_scene.model_dump()
                            premium_scene_data["_model"] = premium_result_or_task.model
                            premium_scene_data["_strategy"] = "premium"
                            
                            # Cache using cache_service.append_event
                            resource = request.resource or ""  # Use empty string if None
                            scene = request.scene if hasattr(request, 'scene') else ""
                            
                            # Cache context_analysis
                            await self.cache_service.append_event(
                                session_id=request.conversation_id,
                                category="context_analysis",
                                resource=resource,
                                payload=premium_context_data,
                                scene=scene
                            )
                            
                            # Cache scene_analysis
                            await self.cache_service.append_event(
                                session_id=request.conversation_id,
                                category="scene_analysis",
                                resource=resource,
                                payload=premium_scene_data,
                                scene=scene
                            )
                            
                            logger.info(f"[{request.conversation_id}] Premium result cached successfully")
                        else:
                            logger.warning(f"[{request.conversation_id}] Premium result invalid, not caching")
                    except Exception as e:
                        logger.warning(f"[{request.conversation_id}] Failed to cache premium result: {e}")
                
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
                text = bubble.get("text", "")
                logger.info(f"[{__name__}:analyze_with_merge_step:L{713}] Bubble text: {text}")
                dialogs.append({
                    "speaker": bubble.get("sender", "user"),
                    "text": text,
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
            # Add metadata for cache logging
            context_data = context.model_dump(mode="json")
            context_data["_model"] = llm_result.model
            context_data["_strategy"] = winning_strategy
            
            scene_data = scene.model_dump(mode="json")
            scene_data["_model"] = llm_result.model
            scene_data["_strategy"] = winning_strategy
            
            if settings.debug.log_cache_operations:
                logger.error(f"[{request.conversation_id}] ===== MULTIMODAL CACHE WRITE DEBUG =====")
                logger.error(f"[{request.conversation_id}] About to cache {winning_strategy} results: resource={request.resource}, resources={request.resources}, scene={request.scene}")
                logger.error(f"[{request.conversation_id}] Multimodal strategy={winning_strategy}, model={llm_result.model}")
                logger.error(f"[{request.conversation_id}] ===== END MULTIMODAL CACHE WRITE DEBUG =====")
            
            # Cache screenshot_parse separately for bbox information
            screenshot_parse_data = {
                "screenshot_parse": parsed_json.get("screenshot_parse", {}),
                "_model": llm_result.model,
                "_strategy": winning_strategy,
            }
            await self._append_cache_event(
                request,
                "screenshot_parse",
                screenshot_parse_data
            )
            
            # Also cache in image_result format for backward compatibility with non-merge_step
            # Convert screenshot_parse bubbles to ImageResult dialogs format
            from app.models.v1_api import DialogItem
            screenshot_data = parsed_json.get("screenshot_parse", {})
            bubbles = screenshot_data.get("bubbles", [])
            dialogs_for_image_result = []
            for bubble in bubbles:
                bbox = bubble.get("bbox", {})
                dialog_item = {
                    "position": [
                        bbox.get("x1", 0),
                        bbox.get("y1", 0),
                        bbox.get("x2", 0),
                        bbox.get("y2", 0),
                    ],
                    "text": bubble.get("text", ""),
                    "speaker": bubble.get("sender", "user"),
                    "from_user": (bubble.get("sender", "user") == "user"),
                }
                dialogs_for_image_result.append(dialog_item)
            
            image_result_data = {
                "content": request.resource or (request.resources[0] if request.resources else ""),
                "dialogs": dialogs_for_image_result,
                "scenario": scene.recommended_scenario,
                "_model": llm_result.model,
                "_strategy": winning_strategy,
            }
            await self._append_cache_event(
                request,
                "image_result",
                image_result_data
            )
            logger.info(f"[{request.conversation_id}] Cached {winning_strategy} image_result for backward compatibility")
            
            await self._append_cache_event(
                request,
                "context_analysis",  # Use traditional field name
                context_data
            )
            logger.info(f"[{request.conversation_id}] Cached {winning_strategy} context_analysis: session_id={request.conversation_id}, resource={request.resource}, scene={request.scene}")
            await self._append_cache_event(
                request,
                "scene_analysis",  # Use traditional field name
                scene_data
            )
            logger.info(f"[{request.conversation_id}] Cached {winning_strategy} scene_analysis: session_id={request.conversation_id}, resource={request.resource}, scene={request.scene}")
            
            logger.info("merge_step analysis completed and cached")
            
            return context, scene, parsed_json  # Return raw parsed_json for bbox extraction
            
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
                logger.info(f"[{request.conversation_id}] Using cached context_analysis")
            else:
                context = await self._execute_step(
                    exec_ctx,
                    "context_builder",
                    self._build_context,
                    request,
                )
                # Add metadata for consistency with merge_step cache
                context_data = context.model_dump(mode="json")
                context_data["_model"] = "non-merge-step"
                context_data["_strategy"] = "traditional"
                await self._append_cache_event(request, "context_analysis", context_data)
            
            # Step 2: Analyze scene (传递 context 以获取当前亲密度)
            cached_scene = await self._get_cached_payload(request, "scene_analysis")
            if cached_scene:
                scene = SceneAnalysisResult(**cached_scene)
                logger.info(f"[{request.conversation_id}] Using cached scene_analysis")
            else:
                scene = await self._execute_step(
                    exec_ctx,
                    "scene_analysis",
                    self._analyze_scene,
                    request,
                    context,  # 传递 context
                )
                # Add metadata for consistency with merge_step cache
                scene_data = scene.model_dump(mode="json")
                scene_data["_model"] = "non-merge-step"
                scene_data["_strategy"] = "traditional"
                await self._append_cache_event(request, "scene_analysis", scene_data)
            
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
                logger.info(f"[{request.conversation_id}] Using cached context_analysis")
            else:
                context = await self._execute_step(
                    exec_ctx,
                    "context_builder",
                    self._build_context,
                    request,
                )
                # Add metadata for consistency with merge_step cache
                context_data = context.model_dump(mode="json")
                context_data["_model"] = "non-merge-step"
                context_data["_strategy"] = "traditional"
                await self._append_cache_event(request, "context_analysis", context_data)
            
            # Step 2: Analyze scene (传递 context 以获取当前亲密度)
            cached_scene = await self._get_cached_payload(request, "scene_analysis")
            if cached_scene:
                scene = SceneAnalysisResult(**cached_scene)
                logger.info(f"[{request.conversation_id}] Using cached scene_analysis")
            else:
                scene = await self._execute_step(
                    exec_ctx,
                    "scene_analysis",
                    self._analyze_scene,
                    request,
                    context,  # 传递 context
                )
                # Add metadata for consistency with merge_step cache
                scene_data = scene.model_dump(mode="json")
                scene_data["_model"] = "non-merge-step"
                scene_data["_strategy"] = "traditional"
                await self._append_cache_event(request, "scene_analysis", scene_data)
            
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
                    reply_sentence=getattr(request, "reply_sentence", ""),  # 新增：传递 reply_sentence
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
            
            if settings.debug.log_cache_operations:
                logger.error(f"[{request.conversation_id}] ===== CACHE READ ATTEMPT =====")
                logger.error(f"[{request.conversation_id}] Reading cache for category={category}, resource_key={resource_key}, scene={request.scene}")
                logger.error(f"[{request.conversation_id}] request.resource={request.resource}, request.resources={request.resources}")
                logger.error(f"[{request.conversation_id}] ===== END CACHE READ ATTEMPT =====")
                
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
                    if settings.debug.log_cache_operations:
                        logger.error(f"[{request.conversation_id}] ===== CACHE HIT DETAILS =====")
                        logger.error(f"[{request.conversation_id}] Cache hit: category={category}, resource={resource_key}")
                        logger.error(f"[{request.conversation_id}] Cached strategy={payload.get('_strategy')}, model={payload.get('_model')}")
                        logger.error(f"[{request.conversation_id}] ===== END CACHE HIT DETAILS =====")
                    return payload
        except Exception as exc:
            logger.warning("Cache read failed for category=%s: %s", category, exc)
        return None

    async def _append_cache_event(self, request: GenerateReplyRequest, category: str, payload: dict) -> None:
        if self.cache_service is None or (not request.resource and not request.resources):
            logger.info(f"[{request.conversation_id}] Skipping cache: cache_service={self.cache_service is not None}, resource={request.resource}, resources={request.resources}")
            return
        try:
            resources = []
            if request.resources:
                resources.extend(request.resources)
            if request.resource:
                resources.append(request.resource)
            
            logger.info(f"[{request.conversation_id}] Caching to resources: {resources}")

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

    def _register_background_task(self, task: asyncio.Task, task_name: str = "unknown") -> None:
        """Register a background task for tracking and cleanup.
        
        Args:
            task: The asyncio Task to register
            task_name: Human-readable name for logging
        """
        self._background_tasks.append(task)
        logger.debug(f"Registered background task: {task_name} (total: {len(self._background_tasks)})")
        
        # Add callback to remove completed tasks
        def on_task_done(t: asyncio.Task):
            try:
                self._background_tasks.remove(t)
                logger.debug(f"Background task completed: {task_name} (remaining: {len(self._background_tasks)})")
            except ValueError:
                pass  # Task already removed
        
        task.add_done_callback(on_task_done)
    
    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown the orchestrator and wait for background tasks.
        
        Args:
            timeout: Maximum time to wait for background tasks (seconds)
        """
        logger.info(f"Orchestrator shutdown initiated. Waiting for {len(self._background_tasks)} background tasks...")
        self._shutdown_event.set()
        
        if not self._background_tasks:
            logger.info("No background tasks to wait for")
            return
        
        try:
            # Wait for all background tasks with timeout
            await asyncio.wait_for(
                asyncio.gather(*self._background_tasks, return_exceptions=True),
                timeout=timeout
            )
            logger.info("All background tasks completed successfully")
        except asyncio.TimeoutError:
            logger.warning(f"Background tasks did not complete within {timeout}s, cancelling...")
            # Cancel remaining tasks
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
            # Wait a bit for cancellation to propagate
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            logger.info("Background tasks cancelled")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def get_background_task_count(self) -> int:
        """Get the number of active background tasks.
        
        Returns:
            Number of active background tasks
        """
        return len(self._background_tasks)
