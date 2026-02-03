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
from fastapi import APIRouter, HTTPException
from typing import Literal, List
from copy import deepcopy
from app.models.v1_api import PredictRequest, PredictResponse, ImageResult, DialogItem, ErrorResponse
from app.services.llm_adapter import LLMAdapterError, LLMCall, create_llm_adapter
from app.core.v1_dependencies import (
    ScreenshotAnalysisServiceDep,
    OrchestratorDep,
    MetricsCollectorDep)
from app.services.screenshot_processor import is_url

from app.core.dependencies import SessionCategorizedCacheServiceDep, ScreenshotParserDep
from app.models.screenshot import ParseScreenshotRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["predict"])

# define (list[str], list[DialogItem], list[ImageResult]) as ImageAnalysisQueueInput
ImageAnalysisQueueInput = tuple[list[str], list[DialogItem], list[ImageResult]]

# define ("image"|"text", ImageResult) as SpecifiedImageResult
SpecifiedImageResult = tuple[Literal["image", "text"], ImageResult]


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
    screenshot_service: ScreenshotAnalysisServiceDep,
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
        screenshot_service: ScreenshotAnalysisService dependency
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
                screenshot_service,
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

async def _get_screenshot_analysis_from_local_service(content_url, lang, screenshot_service: ScreenshotAnalysisServiceDep):
    try:
        dialogs = []
        output_payload = await screenshot_service.analyze_screenshot(content_url, lang)
        logger.info(f"dialogs from screenshot analysis: {output_payload.get('dialogs', [])}")
        for dialog_data in output_payload.get("dialogs", []):
            box = dialog_data.get("box", [0, 0, 0, 0])
            speaker = dialog_data.get("speaker", "unknown")
            from_user = (speaker == "user")
            
            # Create DialogItem with normalized coordinates
            dialog_item = DialogItem(
                position=box,
                text=dialog_data.get("text", ""),
                speaker=speaker,
                from_user=from_user,
            )
            dialogs.append(dialog_item)
        
        # Create image result
        result = ImageResult(
            content=content_url,
            dialogs=dialogs
        )
        
        logger.info(f"Successfully analyzed screenshot: {content_url}")
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing screenshot {content_url}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze screenshot: {str(e)}"
        )

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
            raise Exception("Failed to parse screenshot")
        
        # Create image result
        result = ImageResult(
            content=content_url,
            dialogs=dialogs
        )
        return result
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
    screenshot_service: ScreenshotAnalysisServiceDep,
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
        else:
            try:
                # raise Exception("Failed to get screenshot analysis from cache")
                image_result = await _get_screenshot_analysis_from_local_service(content_url, lang, screenshot_service)
            except Exception:
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
                        reply_text = json.loads(orchestrator_response.reply_text)
                        if isinstance(reply_text, dict):
                            suggested_reply_items = reply_text.get("replies", [])
                            suggested_replies = [item.get("text", "") for item in suggested_reply_items]
                        else:
                            suggested_replies = []
                    except Exception as exc:
                        suggested_replies = []
                        raise ValueError("Failed to parse reply text as JSON") from exc
                logger.info(f"Reply generation successful: {len(suggested_replies)} replies")
            else:
                logger.warning("Orchestrator not available, skipping reply generation")
            
        return suggested_replies
    except Exception as e:
        logger.error(f"Reply generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reply generation failed: {e}")


async def handle_image(
    request: PredictRequest,
    screenshot_service: ScreenshotAnalysisServiceDep,
    screenshot_parser: ScreenshotParserDep,
    orchestrator: OrchestratorDep,
    start_time: float,
    metrics: MetricsCollectorDep,
    cache_service: SessionCategorizedCacheServiceDep,
) -> PredictResponse:
    # Process each content item (image URL)

    items: list[tuple[Literal["image", "text"], str, ImageResult]] = []
    for content_url in request.content:
        try:
            logger.info(f"Processing content: {content_url}")
            if not is_url(content_url):
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
            image_result = await get_screenshot_analysis_result(
                content_url,
                request.language,
                request.session_id,
                request.scene,
                cache_service,
                screenshot_service,
                screenshot_parser,
            )
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
            continue

        current_dialogs = current_dialogs + item_result.dialogs
        current_ImageResultList.append(item_result)
        current_content_keys.append(item_key)
    if current_content_keys or current_dialogs or current_ImageResultList:
        analysis_queue.append((
                deepcopy(current_content_keys),
                deepcopy(current_dialogs),
                deepcopy(current_ImageResultList),
            ))
    results = []
    # If only scene analysis is requested
    if request.scene_analysis and items:
        results = await _scenario_analysis(
            request,
            orchestrator,
            analysis_queue,
        )
    suggested_replies: list[str] = []
    # If reply generation is requested, call Orchestrator
    if request.reply and items:
        suggested_replies = await _generate_reply(
            request,
            orchestrator,
            analysis_queue,
        )

    # Record successful request
    duration_ms = int((time.time() - start_time) * 1000)
    metrics.record_request("predict", 200, duration_ms)
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


async def handle_image_old(
    request: PredictRequest,
    screenshot_service: ScreenshotAnalysisServiceDep,
    screenshot_parser: ScreenshotParserDep,
    orchestrator: OrchestratorDep,
    start_time: float,
    metrics: MetricsCollectorDep,
    cache_service: SessionCategorizedCacheServiceDep,
) -> PredictResponse:
    # Process each content item (image URL)

    results_dict = {}
    for content_url in request.content:
        try:
            logger.info(f"Processing content: {content_url}")
            if not is_url(content_url):
                results_dict[content_url] = [
                    "text",
                    ImageResult(
                        content=content_url,
                        dialogs=[
                            DialogItem(
                                position=[0.0, 0.0, 0.0, 0.0],
                                text=content_url,
                                speaker="",
                                from_user=False,
                            )
                        ],
                    ),
                ]
                continue
            image_result = await get_screenshot_analysis_result(
                content_url,
                request.session_id,
                request.scene,
                cache_service,
                screenshot_service,
                screenshot_parser,
            )
            logger.info(f"Image result: {type(image_result)}")
            logger.info(f"Content processed successfully: {len(image_result.dialogs)} dialogs extracted")
     
            await cache_service.append_event(
                session_id=request.session_id,
                category="image_result",
                resource=content_url,
                payload=image_result.model_dump(mode="json"),
                scene=request.scene,
            )
            results_dict[content_url] = ["image", image_result]
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

        
    # Initialize suggested_replies as None
    suggested_replies = None
    current_scenario = None
    recommended_scenario = None
    recommended_strategies = None

    text_dialogs = []
    talker_nickname = ""
    current_content_keys = []
    current_dialogs = []
    for key, values in results_dict.items():
        if values[0] == "image":
            current_dialogs = current_dialogs + values[1].dialogs
            current_content_keys.append(key)
        elif values[0] == "text":
            current_dialogs = current_dialogs + values[1].dialogs
            current_content_keys.append(key)
    results = []
    # If only scene analysis is requested
    if request.scene_analysis and results_dict:
        try:
            logger.info("Scene analysis requested, calling Orchestrator")

            for url_index, _image_result in enumerate(list(results_dict.values())):
                dialog = _image_result[1].dialogs
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
                        resource=request.content[url_index],
                        dialogs=conversation,
                        language=request.language,
                        quality="normal",
                        persona=request.other_properties,
                        scene=request.scene,
                    )

                    scenario_analysis_result = await orchestrator.scenario_analysis(orchestrator_request)
                    # current_scenario: str = ""  # 当前情景（安全/低风险策略|平衡/中风险策略|高风险/高回报策略|关系修复策略|禁止的策略）
                    # recommended_scenario: str = ""  # 推荐情景
                    # recommended_strategies: list[str] = Field(default_factory=list)  # 推荐的对话策略（3个策略代码）
                    results.append(_image_result[1])
                    results[-1].scenario = f"current scenario:{scenario_analysis_result.current_scenario}, \
                    recommended scenario:{scenario_analysis_result.recommended_scenario}, \
                    recommended strategies:{scenario_analysis_result.recommended_strategies}"
                else:
                    logger.warning("Orchestrator not available, skipping reply generation")
            
        except Exception as e:
            # Requirement 9.5: Handle Orchestrator failures gracefully
            logger.error(f"Reply generation failed: {e}", exc_info=True)
            # Continue without replies - don't fail the entire request

    # If reply generation is requested, call Orchestrator
    if request.reply and results_dict:
        try:
            logger.info("Reply generation requested, calling Orchestrator")
            
            for url_index, _image_result in enumerate(list(results_dict.values())):
                dialog = _image_result[1].dialogs
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
                        resource=request.content[url_index],
                        dialogs=conversation,
                        language=request.language,
                        quality="normal",
                        persona=request.other_properties,
                        scene=request.scene,
                    )

                    orchestrator_response = await orchestrator.generate_reply(orchestrator_request)
                    # Requirement 9.4: Include suggested_replies in response if successful
                    if orchestrator_response and hasattr(orchestrator_response, "reply_text"):
                        try:
                            logger.info(f"Orchestrator response: {orchestrator_response.reply_text}")
                            reply_text = json.loads(orchestrator_response.reply_text)
                            if isinstance(reply_text, dict):
                                suggested_reply_items = reply_text.get("replies", [])
                                suggested_replies = [item.get("text", "") for item in suggested_reply_items]
                            else:
                                suggested_replies = []
                        except Exception as exc:
                            suggested_replies = []
                            raise ValueError("Failed to parse reply text as JSON") from exc
                    logger.info(f"Reply generation successful: {len(suggested_replies)} replies")
                else:
                    logger.warning("Orchestrator not available, skipping reply generation")
            
        except Exception as e:
            # Requirement 9.5: Handle Orchestrator failures gracefully
            logger.error(f"Reply generation failed: {e}", exc_info=True)
            # Continue without replies - don't fail the entire request

    # Record successful request
    duration_ms = int((time.time() - start_time) * 1000)
    metrics.record_request("predict", 200, duration_ms)

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