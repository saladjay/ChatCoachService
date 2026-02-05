"""
Predict endpoint for ChatCoach API v1.

This module provides the POST /api/v1/ChatCoach/predict endpoint that analyzes
chat screenshots and optionally generates reply suggestions.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12,
              7.1, 7.2, 7.3, 7.4, 7.5, 9.1, 9.2, 9.3, 9.4, 9.5
"""

import logging
import time
import json
import os
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import Literal, List
from copy import deepcopy
from urllib.parse import urlparse
from app.models.v1_api import PredictRequest, PredictResponse, ImageResult, DialogItem, ErrorResponse
from app.services.llm_adapter import LLMAdapterError, LLMCall, create_llm_adapter
from app.core.v1_dependencies import (
    OrchestratorDep,
    MetricsCollectorDep)
from app.core.dependencies import SessionCategorizedCacheServiceDep, ScreenshotParserDep
from app.models.screenshot import ParseScreenshotRequest
from app.core.config import settings
from app.observability.trace_logger import trace_logger

logger = logging.getLogger(__name__)

router = APIRouter(tags=["predict"])

# define (list[str], list[DialogItem], list[ImageResult]) as ImageAnalysisQueueInput
ImageAnalysisQueueInput = tuple[list[str], list[DialogItem], list[ImageResult]]


def _log_failed_json_reply(reply_text: str, session_id: str, error_msg: str) -> None:
    """Log failed JSON reply to file for analysis.
    
    Args:
        reply_text: The raw reply text that failed to parse
        session_id: Session ID for tracking
        error_msg: Error message from the exception
    """
    try:
        # Create logs directory if it doesn't exist
        log_dir = Path("logs/failed_json_replies")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = log_dir / f"failed_reply_{timestamp}_{session_id[:8]}.json"
        
        # Prepare log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "error": error_msg,
            "reply_text": reply_text,
            "reply_length": len(reply_text),
        }
        
        # Write to file
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Failed JSON reply logged to: {filename}")
        
    except Exception as e:
        logger.error(f"Failed to log failed JSON reply: {e}")


def parse_json_with_markdown(text: str) -> dict:
    """Parse JSON text that may be wrapped in markdown code blocks.
    
    This function handles various formats:
    - Plain JSON: {"key": "value"}
    - Markdown JSON block: ```json\n{"key": "value"}\n```
    - Markdown code block: ```\n{"key": "value"}\n```
    - JSON with extra text: Some text {"key": "value"} more text
    
    Args:
        text: The text to parse
        
    Returns:
        Parsed JSON object
        
    Raises:
        json.JSONDecodeError: If JSON cannot be parsed
    """
    text = text.strip()
    
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
    
    # Parse JSON
    return json.loads(text)

# define ("image"|"text", ImageResult) as SpecifiedImageResult
SpecifiedImageResult = tuple[Literal["image", "text"], ImageResult]


def _is_url(content: str) -> bool:
    try:
        parsed = urlparse(content)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


@router.post(
    "",
    response_model=PredictResponse,
    responses={
        200: {
            "description": "Screenshot analysis completed successfully",
            "model": PredictResponse,
        },
        400: {
            "description": "Invalid request or image load failed",
            "model": ErrorResponse,
        },
        401: {
            "description": "Models are unavailable",
            "model": ErrorResponse,
        },
        500: {
            "description": "Internal server error or inference failed",
            "model": ErrorResponse,
        },
    },
    summary="Analyze chat screenshots",
    description="""
    Analyze chat screenshots to extract structured conversation data.
    Optionally generate suggested replies using the Orchestrator.
    
    The endpoint:
    1. Validates request parameters (language, scene, etc.)
    2. Processes each screenshot URL to extract dialogs
    3. If reply=true, calls Orchestrator to generate suggested replies
    4. Returns structured results with dialogs and optional replies
    
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12
    """,
)
async def predict(
    request: PredictRequest,
    screenshot_parser: ScreenshotParserDep,
    orchestrator: OrchestratorDep,
    metrics: MetricsCollectorDep,
    cache_service: SessionCategorizedCacheServiceDep,
) -> PredictResponse:
    """
    识别聊天截图中的对话内容并可选生成回复建议
    
    This endpoint performs the following steps:
    1. Validate request parameters (handled by Pydantic model)
    2. Process each screenshot URL to extract dialogs
    3. If reply=true, calls Orchestrator to generate suggested replies
    4. Returns structured results with dialogs and optional replies
    
    Args:
        request: PredictRequest with content, language, scene, user_id, etc.
        screenshot_parser: ScreenshotParserService dependency
        orchestrator: Orchestrator service dependency
        metrics: MetricsCollector service dependency
        cache_service: SessionCategorizedCacheService dependency
    
    Returns:
        PredictResponse with success status, results, and optional suggested_replies
    
    Raises:
        HTTPException: 401 if models unavailable, 400 for validation/image errors,
                      500 for inference errors
    """
    start_time = time.time()
    
    logger.info(
        f"Predict request received: user_id={request.user_id}, "
        f"content={len(request.content)}, scene={request.scene}, "
        f"language={request.language}, reply={request.reply}, "
        f"session_id={request.session_id}, scene_analysis={request.scene_analysis}"
    )
    
    # Log other_properties if provided
    if request.other_properties:
        logger.info(f"other_properties: {request.other_properties}")
    
    # 验证cache中的scene是否符合当前request的scene
    try:
        normalized_scene = 1 if request.scene in (1, 3) else request.scene
        if cache_service is not None:
            cached_scene_event = await cache_service.get_resource_category_last(
                session_id=request.session_id,
                category="scene_type",
                resource="__scene__",
                scene=request.scene,
            )
            if cached_scene_event:
                cached_payload = cached_scene_event.get("payload")
                cached_scene = None
                if isinstance(cached_payload, dict):
                    cached_scene = cached_payload.get("scene")
                if cached_scene is not None and cached_scene != normalized_scene:
                    logger.warning(
                        "Scene mismatch for session %s: cached=%s current=%s",
                        request.session_id,
                        cached_scene,
                        normalized_scene,
                    )
                    
                    raise HTTPException(
                        status_code=400,
                        detail="Scene mismatch for session",
                    )
            else:
                await cache_service.append_event(
                    session_id=request.session_id,
                    category="scene_type",
                    resource="__scene__",
                    payload={"scene": normalized_scene},
                    scene=request.scene,
                )

        # Handle text Q&A scenario (scene == 2)
        if normalized_scene == 2:
            return await handle_text_qa(request, start_time, metrics)
        
        # Handle image and text scenario (scene == 1)
        if normalized_scene == 1:
            return await handle_image(
                request,
                screenshot_parser,
                orchestrator,
                start_time,
                metrics,
                cache_service,
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        # Requirement 7.4, 7.5: Return descriptive error messages and log errors
        logger.exception(f"Unexpected error in predict endpoint: {e}")
        metrics.record_request("predict", 500, int((time.time() - start_time) * 1000))
        
        return PredictResponse(
            success=False,
            message=f"Internal server error: {str(e)}",
            user_id=request.user_id,
            request_id=request.request_id,
            session_id=request.session_id,
            scene=request.scene,
            results=[],
        )


async def _get_screenshot_analysis_from_cache(content_url, session_id, scene, cache_service: SessionCategorizedCacheServiceDep):
    cached_event = await cache_service.get_resource_category_last(
        session_id=session_id,
        category="image_result",
        resource=content_url,
        scene=scene,
    )
    if cached_event:
        cached_payload = cached_event.get("payload")
        if isinstance(cached_payload, dict):
            cached_result = ImageResult(**cached_payload)
            logger.info(f"Using cached result for {content_url}")
            return cached_result
    return None


async def _get_screenshot_analysis_from_cloud_service(content_url, screenshot_parser: ScreenshotParserDep):
    try:
        parser_request = ParseScreenshotRequest(image_url=content_url)
        dialogs = []
        parser_response = await screenshot_parser.parse_screenshot(parser_request)
        if parser_response.code == 0 and parser_response.data is not None:
            for bubble in parser_response.data.bubbles:
                dialog_item = DialogItem(
                    position=[
                        bubble.bbox.x1,
                        bubble.bbox.y1,
                        bubble.bbox.x2,
                        bubble.bbox.y2,
                    ],
                    text=bubble.text,
                    speaker=bubble.sender,
                    from_user=(bubble.sender == "user"),
                )
                dialogs.append(dialog_item)
        else:
            # Include detailed error information from parser response
            error_msg = f"Screenshot parser failed with code {parser_response.code}: {parser_response.msg}"
            logger.error(f"Failed to parse screenshot {content_url}: {error_msg}")
            raise Exception(error_msg)
        
        # Create image result
        result = ImageResult(
            content=content_url,
            dialogs=dialogs
        )
        return result
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except Exception as e:
        logger.error(f"Error analyzing screenshot {content_url}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze screenshot: {str(e)}"
        )


async def get_screenshot_analysis_result(
    content_url, 
    lang,
    session_id,
    scene,
    cache_service: SessionCategorizedCacheServiceDep, 
    screenshot_parser: ScreenshotParserDep,
) -> ImageResult:
    try:
        logger.info(f"Processing content: {content_url}")
        image_result = await _get_screenshot_analysis_from_cache(
            content_url,
            session_id,
            cache_service=cache_service,
            scene=scene,
        )
        if image_result is not None:
            image_result.content = content_url
            return image_result
        image_result = await _get_screenshot_analysis_from_cloud_service(content_url, screenshot_parser)
        if image_result:
            image_result.content = content_url
            return image_result
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to analyze screenshot",
            )
    except Exception as e:
        logger.error(f"Error analyzing screenshot {content_url}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze screenshot: {str(e)}",
        )


async def get_merge_step_analysis_result(
    content_url: str,
    request: PredictRequest,
    orchestrator: OrchestratorDep,
    cache_service: SessionCategorizedCacheServiceDep,
) -> tuple[ImageResult, str]:
    """
    Get analysis result using merge_step optimized flow.
    
    This function uses orchestrator.merge_step_analysis() to perform
    screenshot parsing, context building, and scenario analysis in a single LLM call.
    
    Args:
        content_url: URL of the screenshot image
        request: PredictRequest with user info
        orchestrator: Orchestrator service
        cache_service: Cache service
        
    Returns:
        Tuple of (ImageResult with scenario, scenario_json_string)
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        logger.info(f"Processing content with merge_step: {content_url}")
        
        # Download and encode image
        from app.services.image_fetcher import ImageFetcher
        image_fetcher = ImageFetcher()
        fetched_image = await image_fetcher.fetch_image(content_url)
        
        # Prepare GenerateReplyRequest for orchestrator
        from app.models.api import GenerateReplyRequest
        
        orchestrator_request = GenerateReplyRequest(
            user_id=request.user_id,
            target_id="unknown",
            conversation_id=request.session_id,
            resources=[content_url],
            dialogs=[],
            language=request.language,
            quality="normal",
            persona=request.other_properties.lower() if request.other_properties else "",
            scene=request.scene,
        )
        
        # Call merge_step_analysis
        context, scene = await orchestrator.merge_step_analysis(
            request=orchestrator_request,
            image_base64=fetched_image.base64_data,
            image_width=fetched_image.width,
            image_height=fetched_image.height,
        )
        
        # Convert context.conversation to dialogs
        dialogs = []
        for msg in context.conversation:
            dialog_item = DialogItem(
                position=[0.0, 0.0, 0.0, 0.0],  # Position not available from merge_step
                text=msg.content,
                speaker=msg.speaker,
                from_user=(msg.speaker == "user"),
            )
            dialogs.append(dialog_item)
        
        # Create scenario JSON
        scenario_json = {
            "current_scenario": scene.current_scenario,
            "recommended_scenario": scene.recommended_scenario,
            "recommended_strategies": scene.recommended_strategies,
            "relationship_state": scene.relationship_state,
            "intimacy_level": scene.intimacy_level,
        }
        
        # Create ImageResult
        image_result = ImageResult(
            content=content_url,
            dialogs=dialogs,
            scenario=json.dumps(scenario_json, ensure_ascii=False),
        )
        
        logger.info(f"merge_step analysis completed for {content_url}")
        
        return image_result, json.dumps(scenario_json, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Error in merge_step analysis for {content_url}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"merge_step analysis failed: {str(e)}",
        )


async def _scenario_analysis(
    request: PredictRequest,
    orchestrator: OrchestratorDep,
    analysis_queue:List[ImageAnalysisQueueInput]
) -> List[ImageResult]:
    try:
        logger.info("Scene analysis requested, calling Orchestrator")
        results = []
        for resources, dialog, list_image_result in analysis_queue:
            logger.info(f"Dialog: {dialog}")
            # Requirement 9.2: Format dialogs as conversation history
            conversation = []
            for dialog_item in dialog:
                conversation.append({
                    "speaker": dialog_item.speaker if dialog_item.speaker in ["user", "unknown", "self"] else "talker",
                    "text": dialog_item.text,
                })
            
            logger.info(f'conversation:{conversation}')
            # Requirement 9.3: Call Orchestrator with user_id, conversation, language
            if orchestrator is not None:
                from app.models.api import GenerateReplyRequest
                
                orchestrator_request = GenerateReplyRequest(
                    user_id=request.user_id,
                    target_id="unknown",  # Not available from screenshot, use placeholder
                    conversation_id=request.session_id,
                    resources=resources,
                    dialogs=conversation,
                    language=request.language,
                    quality="normal",
                    persona=request.other_properties.lower(),
                    scene=request.scene,
                )

                scenario_analysis_result = await orchestrator.scenario_analysis(orchestrator_request)
                # current_scenario: str = ""  # 当前情景（安全/低风险策略|平衡/中风险策略|高风险/高回报策略|关系修复策略|禁止的策略）
                # recommended_scenario: str = ""  # 推荐情景
                # recommended_strategies: list[str] = Field(default_factory=list)  # 推荐的对话策略（3个策略代码）
                scenario_json = {
                    "current_scenario": scenario_analysis_result.current_scenario,
                    "recommended_scenario": scenario_analysis_result.recommended_scenario,
                    "recommended_strategies": scenario_analysis_result.recommended_strategies,
                }
                for image_result in list_image_result:

                    image_result.scenario = json.dumps(scenario_json, ensure_ascii=False)
                    results.append(image_result)
            else:
                logger.warning("Orchestrator not available, skipping reply generation")
        
    except Exception as e:
        # Requirement 9.5: Handle Orchestrator failures gracefully
        logger.error(f"Reply generation failed: {e}", exc_info=True)
        # raise HTTPException(status_code=500, detail=f"Reply generation failed: {e}")
        results = []
        raise HTTPException(status_code=500, detail=f"scene analysis failed: {e}")
    return results


async def _merged_scenario_analysis(
    request: PredictRequest,
    orchestrator: OrchestratorDep,
    analysis_queue:List[ImageAnalysisQueueInput]
) -> List[ImageResult]:
    """
    Merged scenario analysis that combines screenshot-analysis, context-build, and scenario-analysis.
    
    This optimized flow:
    1. Takes all parsed screenshots (already done)
    2. Builds unified context from all dialogs
    3. Performs scenario analysis with full context
    
    Args:
        request: PredictRequest with user info
        orchestrator: Orchestrator service
        analysis_queue: Queue of (resources, dialogs, image_results) tuples
    
    Returns:
        List of ImageResult with scenario field populated
    """
    try:
        logger.info("Merged scenario analysis requested, calling Orchestrator with unified context")
        results = []
        
        for resources, dialog, list_image_result in analysis_queue:
            logger.info(f"Processing {len(resources)} resources with {len(dialog)} dialog items")
            
            # Format dialogs as conversation history
            conversation = []
            for dialog_item in dialog:
                conversation.append({
                    "speaker": dialog_item.speaker if dialog_item.speaker in ["user", "unknown", "self"] else "talker",
                    "text": dialog_item.text,
                })
            
            logger.info(f'Unified conversation: {len(conversation)} messages')
            
            # Call Orchestrator with unified context (resources list instead of single resource)
            if orchestrator is not None:
                from app.models.api import GenerateReplyRequest
                
                orchestrator_request = GenerateReplyRequest(
                    user_id=request.user_id,
                    target_id="unknown",
                    conversation_id=request.session_id,
                    resources=resources,  # Pass all resources for unified context
                    dialogs=conversation,
                    language=request.language,
                    quality="normal",
                    persona=request.other_properties.lower(),
                    scene=request.scene,
                )

                # Single orchestrator call with merged context
                scenario_analysis_result = await orchestrator.scenario_analysis(orchestrator_request)
                
                scenario_json = {
                    "current_scenario": scenario_analysis_result.current_scenario,
                    "recommended_scenario": scenario_analysis_result.recommended_scenario,
                    "recommended_strategies": scenario_analysis_result.recommended_strategies,
                }
                
                # Apply same scenario result to all images in this group
                for image_result in list_image_result:
                    image_result.scenario = json.dumps(scenario_json, ensure_ascii=False)
                    results.append(image_result)
            else:
                logger.warning("Orchestrator not available, skipping scenario analysis")
        
        logger.info(f"Merged scenario analysis completed for {len(results)} images")
        return results
        
    except Exception as e:
        logger.error(f"Merged scenario analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Merged scenario analysis failed: {e}")


async def _generate_reply(
    request: PredictRequest,
    orchestrator: OrchestratorDep,
    analysis_queue:List[ImageAnalysisQueueInput]
) -> List[str]:
    try:
        logger.info("Reply generation requested, calling Orchestrator")
        suggested_replies: list[str] = []
        
        for resource_index, (resources, dialog, list_image_result) in enumerate(analysis_queue):
            logger.info(f"Dialog: {dialog}")
            # Requirement 9.2: Format dialogs as conversation history
            conversation = []
            for dialog_item in dialog:
                conversation.append({
                    "speaker": dialog_item.speaker,
                    "text": dialog_item.text,
                })
            
            logger.info(f'conversation:{conversation}')
            # Requirement 9.3: Call Orchestrator with user_id, conversation, language
            if orchestrator is not None:
                from app.models.api import GenerateReplyRequest
                
                orchestrator_request = GenerateReplyRequest(
                    user_id=request.user_id,
                    target_id="unknown",  # Not available from screenshot, use placeholder
                    conversation_id=request.session_id,
                    resources=resources,
                    dialogs=conversation,
                    language=request.language,
                    quality="normal",
                    persona=request.other_properties.lower(),
                    scene=request.scene,
                )
                if resource_index < len(analysis_queue) - 1:
                    await orchestrator.prepare_generate_reply(orchestrator_request)
                    continue

                orchestrator_response = await orchestrator.generate_reply(orchestrator_request)
                # Requirement 9.4: Include suggested_replies in response if successful
                if orchestrator_response and hasattr(orchestrator_response, "reply_text"):
                    try:
                        logger.info(f"Orchestrator response: {orchestrator_response.reply_text}")
                        
                        # Parse JSON with markdown code block handling
                        reply_text = parse_json_with_markdown(orchestrator_response.reply_text)
                        
                        if isinstance(reply_text, dict):
                            suggested_reply_items = reply_text.get("replies", [])
                            suggested_replies = [item.get("text", "") for item in suggested_reply_items]
                        else:
                            suggested_replies = []
                            
                    except json.JSONDecodeError as exc:
                        logger.error(f"Failed to parse reply text as JSON: {orchestrator_response.reply_text[:200]}")
                        
                        # Log full failed JSON to file if enabled
                        if settings.log_failed_json_replies:
                            _log_failed_json_reply(
                                orchestrator_response.reply_text,
                                request.session_id,
                                str(exc)
                            )
                        
                        suggested_replies = []
                        raise ValueError(f"Failed to parse reply text as JSON: {str(exc)}") from exc
                    except Exception as exc:
                        logger.error(f"Unexpected error parsing reply: {exc}")
                        
                        # Log full failed JSON to file if enabled
                        if settings.log_failed_json_replies:
                            _log_failed_json_reply(
                                orchestrator_response.reply_text,
                                request.session_id,
                                str(exc)
                            )
                        
                        suggested_replies = []
                        raise ValueError(f"Failed to process reply text: {str(exc)}") from exc
                        
                logger.info(f"Reply generation successful: {len(suggested_replies)} replies")
            else:
                logger.warning("Orchestrator not available, skipping reply generation")
            
        return suggested_replies
    except Exception as e:
        logger.error(f"Reply generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reply generation failed: {e}")


async def handle_image(
    request: PredictRequest,
    screenshot_parser: ScreenshotParserDep,
    orchestrator: OrchestratorDep,
    start_time: float,
    metrics: MetricsCollectorDep,
    cache_service: SessionCategorizedCacheServiceDep,
) -> PredictResponse:
    """
    Handle image processing with optional merge_step optimization.
    
    Flow depends on USE_MERGE_STEP configuration:
    
    Traditional flow (USE_MERGE_STEP=false):
    1. Parse all screenshots separately (screenshot-analysis)
    2. Build unified context from all dialogs (context-build)
    3. Perform scenario analysis with full context (scenario-analysis)
    4. Optionally generate replies
    
    Merge step flow (USE_MERGE_STEP=true):
    1. Use merge_step for each screenshot (combines parsing, context, scenario)
    2. Optionally generate replies
    """
    # Check if merge_step is enabled
    use_merge_step = settings.use_merge_step
    
    if use_merge_step:
        logger.info("Using merge_step optimized flow")
    else:
        logger.info("Using traditional separate flow")
    
    # Step 1: Process all screenshots
    items: list[tuple[Literal["image", "text"], str, ImageResult]] = []
    for content_url in request.content:
        try:
            logger.info(f"Processing content: {content_url}")
            if not _is_url(content_url):
                text_result = ImageResult(
                    content=content_url,
                    dialogs=[
                        DialogItem(
                            position=[0.0, 0.0, 0.0, 0.0],
                            text=content_url,
                            speaker="",
                            from_user=False,
                        )
                    ],
                )
                items.append(("text", content_url, text_result))
                continue
            
            # Time screenshot analysis with trace logging
            screenshot_start = time.time()
            
            # Log screenshot analysis start
            trace_logger.log_event({
                "level": "debug",
                "type": "screenshot_start",
                "task_type": "merge_step" if use_merge_step else "screenshot_parse",
                "url": content_url,
                "session_id": request.session_id,
                "user_id": request.user_id,
            })
            
            # Choose flow based on configuration
            if use_merge_step:
                # Use merge_step optimized flow
                image_result, scenario_json = await get_merge_step_analysis_result(
                    content_url,
                    request,
                    orchestrator,
                    cache_service,
                )
            else:
                # Use traditional separate flow
                image_result = await get_screenshot_analysis_result(
                    content_url,
                    request.language,
                    request.session_id,
                    request.scene,
                    cache_service,
                    screenshot_parser,
                )
            
            screenshot_duration_ms = int((time.time() - screenshot_start) * 1000)
            
            # Log screenshot analysis end with trace
            trace_logger.log_event({
                "level": "debug",
                "type": "screenshot_end",
                "task_type": "merge_step" if use_merge_step else "screenshot_parse",
                "url": content_url,
                "session_id": request.session_id,
                "user_id": request.user_id,
                "duration_ms": screenshot_duration_ms,
            })
            
            logger.info(f"Screenshot analysis completed in {screenshot_duration_ms}ms for {content_url}")
            
            image_result.content = content_url
            logger.info(f"Image result: {type(image_result)}")
            logger.info(f"Content processed successfully: {len(image_result.dialogs)} dialogs extracted")
     
            await cache_service.append_event(
                session_id=request.session_id,
                category="image_result",
                resource=content_url,
                payload=image_result.model_dump(mode="json"),
                scene=request.scene,
            )
            items.append(("image", content_url, image_result))
        except Exception as e:
            error_msg = str(e)
            
            # Determine error type and handle accordingly
            if (
                isinstance(e, LLMAdapterError)
                or "model unavailable" in error_msg.lower()
                or "provider not configured" in error_msg.lower()
                or "all providers failed" in error_msg.lower()
                or "not available" in error_msg.lower()
            ):
                # Requirement 7.1: Handle model unavailable errors (HTTP 401)
                logger.error(f"Model unavailable for {content_url}: {e}")
                metrics.record_request("predict", 401, int((time.time() - start_time) * 1000))
                
                raise HTTPException(
                    status_code=401,
                    detail="Model Unavailable",
                )
            
            elif "load" in error_msg.lower() or "download" in error_msg.lower():
                # Requirement 7.2: Handle image load errors (HTTP 400)
                logger.error(f"Image load failed for {content_url}: {e}")
                metrics.record_request("predict", 400, int((time.time() - start_time) * 1000))
                
                return PredictResponse(
                    success=False,
                    message=f"Load image failed: {str(e)}",
                    user_id=request.user_id,
                    request_id=request.request_id,
                    session_id=request.session_id,
                    scene=request.scene,
                    results=[],
                )
            
            else:
                # Requirement 7.3: Handle inference errors (HTTP 500)
                logger.error(f"Inference failed for {content_url}: {e}", exc_info=True)
                metrics.record_request("predict", 500, int((time.time() - start_time) * 1000))
                
                return PredictResponse(
                    success=False,
                    message=f"Inference error: {str(e)}",
                    user_id=request.user_id,
                    request_id=request.request_id,
                    session_id=request.session_id,
                    scene=request.scene,
                    results=[],
                )

    # If merge_step is enabled and we have results, return them directly
    if use_merge_step and items:
        # Extract results from items
        results = [item_result for _, _, item_result in items]
        
        # Handle reply generation if requested
        suggested_replies: list[str] = []
        if request.reply:
            # Build analysis queue for reply generation
            current_content_keys = []
            current_dialogs = []
            current_ImageResultList = []
            analysis_queue:List[ImageAnalysisQueueInput] = []
            
            for kind, item_key, item_result in items:
                if kind == "image":
                    if current_content_keys or current_dialogs or current_ImageResultList:
                        analysis_queue.append((
                            deepcopy(current_content_keys),
                            deepcopy(current_dialogs),
                            deepcopy(current_ImageResultList),
                        ))
                        current_content_keys = []
                        current_dialogs = []
                        current_ImageResultList = []
                    current_dialogs = current_dialogs + item_result.dialogs
                    current_ImageResultList.append(item_result)
                    current_content_keys.append(item_key)
                else:
                    current_dialogs = current_dialogs + item_result.dialogs
                    current_ImageResultList.append(item_result)
                    current_content_keys.append(item_key)
            
            if current_content_keys or current_dialogs or current_ImageResultList:
                analysis_queue.append((
                    deepcopy(current_content_keys),
                    deepcopy(current_dialogs),
                    deepcopy(current_ImageResultList),
                ))
            
            reply_start = time.time()
            suggested_replies = await _generate_reply(
                request,
                orchestrator,
                analysis_queue,
            )
            reply_duration_ms = int((time.time() - reply_start) * 1000)
            logger.info(f"Reply generation completed in {reply_duration_ms}ms")
        
        # Record successful request
        duration_ms = int((time.time() - start_time) * 1000)
        metrics.record_request("predict", 200, duration_ms)
        
        logger.info(f"merge_step flow completed in {duration_ms}ms")
        
        return PredictResponse(
            success=True,
            message="成功",
            user_id=request.user_id,
            request_id=request.request_id,
            session_id=request.session_id,
            scene=request.scene,
            results=results,
            suggested_replies=suggested_replies,
        )
    
    # Traditional flow continues below
    # Step 2: Build unified analysis queue with merged context
    # Group consecutive text items with the next image, or create separate groups for images
    current_content_keys = []
    current_dialogs = []
    current_ImageResultList = []
    analysis_queue:List[ImageAnalysisQueueInput] = []
    
    for kind, item_key, item_result in items:
        if kind == "image":
            # When we hit an image, finalize any pending group and start a new one
            if current_content_keys or current_dialogs or current_ImageResultList:
                analysis_queue.append((
                    deepcopy(current_content_keys),
                    deepcopy(current_dialogs),
                    deepcopy(current_ImageResultList),
                ))
                current_content_keys = []
                current_dialogs = []
                current_ImageResultList = []

            # Add image to current group
            current_dialogs = current_dialogs + item_result.dialogs
            current_ImageResultList.append(item_result)
            current_content_keys.append(item_key)
            continue

        # Text items accumulate until we hit an image
        current_dialogs = current_dialogs + item_result.dialogs
        current_ImageResultList.append(item_result)
        current_content_keys.append(item_key)
    
    # Don't forget the last group
    if current_content_keys or current_dialogs or current_ImageResultList:
        analysis_queue.append((
                deepcopy(current_content_keys),
                deepcopy(current_dialogs),
                deepcopy(current_ImageResultList),
            ))
    
    results = []
    # Step 3: Perform merged scenario analysis if requested
    if request.scene_analysis and items:
        scenario_start = time.time()
        results = await _merged_scenario_analysis(
            request,
            orchestrator,
            analysis_queue,
        )
        scenario_duration_ms = int((time.time() - scenario_start) * 1000)
        logger.info(f"Merged scenario analysis completed in {scenario_duration_ms}ms")
    
    suggested_replies: list[str] = []
    # Step 4: Generate replies if requested
    if request.reply and items:
        reply_start = time.time()
        suggested_replies = await _generate_reply(
            request,
            orchestrator,
            analysis_queue,
        )
        reply_duration_ms = int((time.time() - reply_start) * 1000)
        logger.info(f"Reply generation completed in {reply_duration_ms}ms")

    # Record successful request
    duration_ms = int((time.time() - start_time) * 1000)
    metrics.record_request("predict", 200, duration_ms)
    
    if results:
        logger.info(f'result scenario:{results[0].scenario}')
    
    # Return successful response
    return PredictResponse(
        success=True,
        message="成功",
        user_id=request.user_id,
        request_id=request.request_id,
        session_id=request.session_id,
        scene=request.scene,
        results=results,
        suggested_replies=suggested_replies,
    )

async def handle_text_qa(
    request: PredictRequest,
    start_time: float,
    metrics: MetricsCollectorDep,
) -> PredictResponse:
    question = "\n".join([c.strip() for c in request.content if c and c.strip()])
    if not question:
        metrics.record_request(
            "predict",
            400,
            int((time.time() - start_time) * 1000),
        )
        return PredictResponse(
            success=False,
            message="Empty question content",
            user_id=request.user_id,
            request_id=request.request_id,
            session_id=request.session_id,
            scene=request.scene,
            results=[],
        )

    if request.language == "zh":
        prompt = f"请用中文回答用户问题。\n\n用户问题：\n{question}\n"
    else:
        prompt = f"Answer the user's question clearly and helpfully.\n\nUser question:\n{question}\n"

    try:
        llm_adapter = create_llm_adapter()
        llm_result = await llm_adapter.call(
            LLMCall(
                task_type="generation",
                prompt=prompt,
                quality="normal",
                user_id=request.user_id,
            )
        )

        duration_ms = int((time.time() - start_time) * 1000)
        metrics.record_request("predict", 200, duration_ms)

        return PredictResponse(
            success=True,
            message="成功",
            user_id=request.user_id,
            request_id=request.request_id,
            session_id=request.session_id,
            scene=request.scene,
            results=[
                ImageResult(
                    content=question,
                    dialogs=[
                        DialogItem(
                            position=[0.0, 0.0, 1.0, 1.0],
                            text=question,
                            speaker="user",
                            from_user=True,
                        )
                    ],
                    scenario="",
                )
            ],
            suggested_replies=[llm_result.text],
        )

    except LLMAdapterError as e:
        logger.error(f"Text Q&A LLM call failed: {e}")
        metrics.record_request(
            "predict",
            500,
            int((time.time() - start_time) * 1000),
        )
        return PredictResponse(
            success=False,
            message=f"LLM error: {str(e)}",
            user_id=request.user_id,
            request_id=request.request_id,
            session_id=request.session_id,
            scene=request.scene,
            results=[],
        )

    except Exception as e:
        logger.exception(f"Text Q&A failed: {e}")
        metrics.record_request(
            "predict",
            500,
            int((time.time() - start_time) * 1000),
        )
        return PredictResponse(
            success=False,
            message=f"Internal server error: {str(e)}",
            user_id=request.user_id,
            request_id=request.request_id,
            session_id=request.session_id,
            scene=request.scene,
            results=[],
        )