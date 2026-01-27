"""
Predict endpoint for ChatCoach API v1.

This module provides the POST /api/v1/ChatCoach/predict endpoint that analyzes
chat screenshots and optionally generates reply suggestions.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12,
              7.1, 7.2, 7.3, 7.4, 7.5, 9.1, 9.2, 9.3, 9.4, 9.5
"""

import logging
import time

from fastapi import APIRouter, HTTPException

from app.models.v1_api import PredictRequest, PredictResponse, ImageResult, DialogItem, ErrorResponse
from app.core.v1_dependencies import (
    ScreenshotAnalysisServiceDep,
    OrchestratorDep,
    MetricsCollectorDep,
)


logger = logging.getLogger(__name__)

router = APIRouter(tags=["predict"])


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
    orchestrator: OrchestratorDep,
    metrics: MetricsCollectorDep,
) -> PredictResponse:
    """
    识别聊天截图中的对话内容并可选生成回复建议
    
    This endpoint performs the following steps:
    1. Validate request parameters (handled by Pydantic model)
    2. Process each screenshot URL using analyze_chat_image
    3. Extract structured dialog data (position, text, speaker, from_user)
    4. If reply=true, format dialogs and call Orchestrator
    5. Return unified response with results and optional suggested_replies
    
    Args:
        request: PredictRequest with content, language, scene, user_id, etc.
        screenshot_service: ScreenshotAnalysisService dependency
        orchestrator: Orchestrator service dependency
        metrics: MetricsCollector service dependency
    
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
        f"session_id={request.session_id}"
    )
    
    # Log other_properties if provided
    if request.other_properties:
        logger.info(f"other_properties: {request.other_properties}")
    
    try:
        # Process each content item (image URL)
        results: list[ImageResult] = []
        all_dialogs = []
        
        for content_url in request.content:
            try:
                logger.info(f"Processing content: {content_url}")
                
                # Use analyze_chat_image to process screenshot
                output_payload = await screenshot_service.analyze_screenshot(content_url)
                
                
                # Convert output_payload to ImageResult with DialogItem objects
                dialogs = []
                for dialog_data in output_payload.get("dialogs", []):
                    # Extract box coordinates (in pixels)
                    box = dialog_data.get("box", [0, 0, 0, 0])
                    
                    # Get speaker and determine from_user
                    speaker = dialog_data.get("speaker", "user")
                    from_user = (speaker == "self")
                    
                    # Create DialogItem with normalized coordinates
                    dialog_item = DialogItem(
                        position=box,
                        text=dialog_data.get("text", ""),
                        speaker=speaker,
                        from_user=from_user,
                    )
                    dialogs.append(dialog_item)
                    all_dialogs.append(dialog_item)
                
                # Get scenario from output_payload or use default
                scenario = output_payload.get("scenario", "")
                
                image_result = ImageResult(
                    content=content_url,
                    dialogs=dialogs,
                    scenario=scenario
                )
                
                results.append(image_result)
                logger.info(f"Content processed successfully: {len(dialogs)} dialogs extracted")
                
            except Exception as e:
                error_msg = str(e)
                
                # Determine error type and handle accordingly
                if "not available" in error_msg.lower() or "model" in error_msg.lower():
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
        
        # If reply generation is requested, call Orchestrator
        # Requirements: 3.8, 3.9, 3.11, 9.1, 9.2, 9.3, 9.4, 9.5
        if request.reply and all_dialogs:
            try:
                logger.info("Reply generation requested, calling Orchestrator")
                
                # Requirement 9.2: Format dialogs as conversation history
                conversation = []
                for dialog in all_dialogs:
                    conversation.append({
                        "speaker": dialog.speaker,
                        "text": dialog.text,
                    })
                
                # Requirement 9.3: Call Orchestrator with user_id, conversation, language
                if orchestrator is not None:
                    from app.models.api import GenerateReplyRequest
                    
                    orchestrator_request = GenerateReplyRequest(
                        user_id=request.user_id,
                        target_id="unknown",  # Not available from screenshot, use placeholder
                        conversation_id=request.session_id,
                        dialogs=conversation,
                        language=request.language,
                        quality="normal",
                    )
                    
                    orchestrator_response = await orchestrator.generate_reply(orchestrator_request)
                    
                    # Requirement 9.4: Include suggested_replies in response if successful
                    if orchestrator_response and hasattr(orchestrator_response, 'reply_text'):
                        suggested_replies = [orchestrator_response.reply_text]
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
