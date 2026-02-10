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
import asyncio
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
    
    This saves the COMPLETE raw response from LLM that failed to parse as JSON.
    This is crucial for debugging why the LLM returned invalid JSON.
    
    Args:
        reply_text: The raw reply text that failed to parse (COMPLETE LLM response)
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
        
        # Prepare log entry with COMPLETE information
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "error": error_msg,
            "raw_text": reply_text,  # Complete raw text from LLM
            "raw_text_length": len(reply_text),
            "truncated_preview": reply_text[:500],  # Preview first 500 chars
            "source": "generation_reply_parser",
        }
        
        # Write to file
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False)
        
        logger.warning(
            f"Failed JSON reply saved to {filename}. "
            f"Response length: {len(reply_text)} chars. "
            f"Review this file to understand why JSON parsing failed."
        )
        
    except Exception as e:
        logger.error(f"Failed to log failed JSON reply: {e}")


def _wrap_plain_text_as_json(text: str) -> dict:
    """Wrap plain text response as JSON for reply generation.
    
    This is a fallback when LLM returns plain text instead of JSON.
    Common cases: "好的，我明白了。" or other acknowledgment text.
    
    Args:
        text: Plain text response from LLM
        
    Returns:
        JSON object with the text wrapped as a single reply
    """
    logger.warning(
        f"LLM returned plain text instead of JSON. Wrapping as fallback. "
        f"Text: {text[:100]}"
    )
    return {
        "replies": [
            {
                "text": text.strip(),
                "strategy": "direct_response",
                "reasoning": "LLM returned plain text, wrapped automatically"
            }
        ]
    }


def parse_json_with_markdown(text: str) -> dict:
    """Parse JSON text that may be wrapped in markdown code blocks.
    
    This function handles various formats with multiple fallback strategies:
    1. Direct JSON parsing
    2. Enhanced JSON repair (removes markdown, fixes brackets, trailing commas)
    3. Markdown code block extraction (```json ... ```)
    4. Simple code block extraction (``` ... ```)
    5. JSON object extraction from text
    6. Stack-based complete JSON extraction (most reliable)
    7. Plain text wrapping (final fallback for reply generation)
    
    Args:
        text: The text to parse
        
    Returns:
        Parsed JSON object
        
    Raises:
        json.JSONDecodeError: If JSON cannot be parsed after all attempts
    """
    original_text = text
    text = text.strip()
    
    # Strategy 1: Try direct JSON parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Enhanced JSON repair (inspired by json-repair library)
    # This handles common LLM issues: markdown wrappers, unclosed brackets, trailing commas
    try:
        repaired = _repair_json_string(text)
        if repaired != text:  # Only try if we actually repaired something
            return json.loads(repaired)
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Strategy 3: Remove markdown JSON code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            extracted = text[start:end].strip()
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                # Try repairing the extracted content
                try:
                    repaired = _repair_json_string(extracted)
                    return json.loads(repaired)
                except (json.JSONDecodeError, ValueError):
                    pass
    
    # Strategy 4: Remove simple markdown code blocks
    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            extracted = text[start:end].strip()
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                # Try repairing the extracted content
                try:
                    repaired = _repair_json_string(extracted)
                    return json.loads(repaired)
                except (json.JSONDecodeError, ValueError):
                    pass
    
    # Strategy 5: Extract JSON object with simple regex
    if "{" in text:
        start = text.find("{")
        end = text.rfind("}") + 1
        if end > start:
            extracted = text[start:end]
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                # Try repairing the extracted content
                try:
                    repaired = _repair_json_string(extracted)
                    return json.loads(repaired)
                except (json.JSONDecodeError, ValueError):
                    pass
    
    # Strategy 6: Use stack-based extraction (most reliable)
    json_objects = _extract_complete_json_objects(text)
    for json_str in json_objects:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try repairing each extracted object
            try:
                repaired = _repair_json_string(json_str)
                return json.loads(repaired)
            except (json.JSONDecodeError, ValueError):
                continue
    
    # Strategy 7: Final fallback - wrap plain text as JSON
    # This handles cases where LLM returns acknowledgment text like "好的，我明白了。"
    if original_text and len(original_text) < 500:  # Only wrap short responses
        return _wrap_plain_text_as_json(original_text)
    
    # All strategies failed
    raise json.JSONDecodeError(
        f"Could not extract valid JSON from response after all attempts. "
        f"Text preview: {original_text[:200]}...",
        original_text,
        0
    )


def _repair_json_string(text: str) -> str:
    """Repair common JSON formatting issues from LLM responses.
    
    This function implements heuristics inspired by json-repair library to fix:
    - Markdown code fences (```json ... ```)
    - Unclosed brackets/braces
    - Trailing commas
    - Missing quotes around keys
    - Incomplete strings
    
    Args:
        text: Potentially malformed JSON string
        
    Returns:
        Repaired JSON string
    """
    if not text:
        return text
    
    original = text
    text = text.strip()
    
    # Step 1: Remove markdown code fences
    # Handle ```json\n{...}\n```
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line if it's a code fence
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        # Remove last line if it's a code fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    # Step 2: Remove leading/trailing backticks
    text = text.strip("`").strip()
    
    # Step 3: Fix unclosed strings (common issue)
    # Count quotes to see if we have an odd number
    quote_count = text.count('"') - text.count('\\"')
    if quote_count % 2 == 1:
        # Odd number of quotes - try to close the last string
        # Find the last quote and add a closing quote before the next structural character
        last_quote_idx = text.rfind('"')
        if last_quote_idx != -1:
            # Look for the next structural character after the last quote
            remaining = text[last_quote_idx + 1:]
            for i, char in enumerate(remaining):
                if char in [',', '}', ']', '\n']:
                    text = text[:last_quote_idx + 1 + i] + '"' + text[last_quote_idx + 1 + i:]
                    break
    
    # Step 4: Fix unclosed brackets/braces
    # Count opening and closing brackets
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')
    
    # Add missing closing braces
    if open_braces > close_braces:
        text += '}' * (open_braces - close_braces)
    
    # Add missing closing brackets
    if open_brackets > close_brackets:
        text += ']' * (open_brackets - close_brackets)
    
    # Step 5: Remove trailing commas before closing braces/brackets
    # This is a common LLM mistake
    import re
    # Remove comma before }
    text = re.sub(r',(\s*})', r'\1', text)
    # Remove comma before ]
    text = re.sub(r',(\s*])', r'\1', text)
    
    # Step 6: Fix common key formatting issues
    # Replace single quotes with double quotes (only for keys)
    # This is a simplified approach - a full implementation would need proper parsing
    text = re.sub(r"'([^']+)'(\s*):", r'"\1"\2:', text)
    
    # Step 7: Remove comments (// and /* */)
    # Remove single-line comments
    text = re.sub(r'//[^\n]*\n', '\n', text)
    # Remove multi-line comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    
    return text
    # Strategy 6: Final fallback - wrap plain text as JSON
    # This handles cases where LLM returns acknowledgment text like "好的，我明白了。"
    if original_text and len(original_text) < 500:  # Only wrap short responses
        return _wrap_plain_text_as_json(original_text)
    
    # All strategies failed
    raise json.JSONDecodeError(
        f"Could not extract valid JSON from response after all attempts. "
        f"Text preview: {original_text[:200]}...",
        original_text,
        0
    )


def _extract_complete_json_objects(text: str) -> list[str]:
    """Extract all complete JSON objects from text using stack-based bracket matching.
    
    This method finds properly balanced JSON objects by tracking opening and closing braces.
    It's more reliable than regex for extracting complete JSON structures.
    
    Args:
        text: Text that may contain JSON objects
        
    Returns:
        List of JSON object strings (properly balanced braces)
    """
    results = []
    stack = []
    start_idx = None
    in_string = False
    escape_next = False
    
    for i, char in enumerate(text):
        # Handle string escaping
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        # Track if we're inside a string (to ignore braces in strings)
        if char == '"':
            in_string = not in_string
            continue
        
        # Only process braces outside of strings
        if not in_string:
            if char == '{':
                if not stack:
                    start_idx = i
                stack.append('{')
            elif char == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
                    if not stack and start_idx is not None:
                        # Found a complete JSON object
                        results.append(text[start_idx:i+1])
                        start_idx = None
    
    return results

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
    logger.info(f"[TIMING] predict function started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    
    # Log request start with trace
    if trace_logger.should_log_timing():
        trace_logger.log_event({
            "level": "debug",
            "type": "predict_start",
            "user_id": request.user_id,
            "content_count": len(request.content),
            "scene": request.scene,
            "language": request.language,
            "reply": request.reply,
            "session_id": request.session_id,
            "scene_analysis": request.scene_analysis,
        })
    
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
            result = await handle_text_qa(request, start_time, metrics)
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[TIMING] predict function ended (text_qa) at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}, duration: {duration_ms}ms")
            return result
        
        # Handle image and text scenario (scene == 1)
        if normalized_scene == 1:
            result = await handle_image(
                request,
                screenshot_parser,
                orchestrator,
                start_time,
                metrics,
                cache_service,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"result: {result.results}")
            
            # Log result summary (always)
            for idx, img_result in enumerate(result.results):
                dialog_count = len(img_result.dialogs) if img_result.dialogs else 0
                scenario_preview = img_result.scenario[:100] if img_result.scenario else "None"
                logger.info(f"result[{idx}]: {dialog_count} dialogs, scenario: {scenario_preview}...")
            
            # Log full content if debug flag is enabled
            if settings.debug_config.log_full_result_content:
                for idx, img_result in enumerate(result.results):
                    logger.debug(f"result[{idx}] full content:")
                    logger.debug(f"  content URL: {img_result.content}")
                    logger.debug(f"  scenario: {img_result.scenario}")
                    logger.debug(f"  dialogs ({len(img_result.dialogs) if img_result.dialogs else 0}):")
                    if img_result.dialogs:
                        for dialog_idx, dialog in enumerate(img_result.dialogs):
                            text_preview = dialog.text[:200] if len(dialog.text) > 200 else dialog.text
                            logger.debug(f"    [{dialog_idx}] {dialog.speaker}: {text_preview}{'...' if len(dialog.text) > 200 else ''}")
            
            logger.info(f"[TIMING] predict function ended (image) at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}, duration: {duration_ms}ms")
            return result
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        # Requirement 7.4, 7.5: Return descriptive error messages and log errors
        duration_ms = int((time.time() - start_time) * 1000)
        logger.exception(f"Unexpected error in predict endpoint: {e}")
        logger.info(f"[TIMING] predict function ended with error at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}, duration: {duration_ms}ms")
        metrics.record_request("predict", 500, duration_ms)
        
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
        
        # Get image format configuration
        from app.core.config import settings
        image_format = settings.llm.multimodal_image_format
        
        # Prepare image data based on format
        if image_format == "url":
            # URL format: Try to get cached dimensions, otherwise use placeholders
            # LLM will download the image directly from URL
            from app.services.image_dimension_fetcher import get_dimension_fetcher
            
            dimension_fetcher = get_dimension_fetcher()
            cached_dimensions = await dimension_fetcher.get_cached_dimensions(
                url=content_url,
                cache_service=cache_service,
                session_id=request.session_id,
                scene=request.scene,
            )
            
            if cached_dimensions:
                image_width, image_height = cached_dimensions
                logger.info(f"Using cached dimensions: {image_width}x{image_height}")
            else:
                # Use placeholders and start background task to fetch real dimensions
                image_width = 1080  # Placeholder - typical mobile screenshot width
                image_height = 1920  # Placeholder - typical mobile screenshot ratio
                logger.info(f"Using placeholder dimensions: {image_width}x{image_height}")
                
                # Start background task to fetch and cache real dimensions
                asyncio.create_task(
                    dimension_fetcher.fetch_and_cache(
                        url=content_url,
                        cache_service=cache_service,
                        session_id=request.session_id,
                        scene=request.scene,
                    )
                )
                logger.info(f"Started background task to fetch dimensions for {content_url}")
            
            image_base64 = None  # Not needed for URL format
            
            logger.info(f"Using URL format (skipping download): {content_url}")
        else:
            # Base64 format: Download image (compress based on configuration)
            from app.services.image_fetcher import ImageFetcher
            image_fetcher = ImageFetcher()
            
            # Use configuration to determine if compression is needed
            compress = settings.llm.multimodal_image_compress
            fetched_image = await image_fetcher.fetch_image(content_url, compress=compress)
            image_width = fetched_image.width
            image_height = fetched_image.height
            image_base64 = fetched_image.base64_data
            
            compress_status = "compressed" if compress else "original"
            logger.info(f"Using base64 format ({compress_status}): {image_width}x{image_height}")
        
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
        context, scene, parsed_json = await orchestrator.merge_step_analysis(
            request=orchestrator_request,
            image_url=content_url,
            image_base64=image_base64,
            image_width=image_width,
            image_height=image_height,
        )
        
        # Extract bubbles with bbox information from parsed_json
        screenshot_data = parsed_json.get("screenshot_parse", {})
        bubbles = screenshot_data.get("bubbles", [])
        
        # Convert context.conversation to dialogs with bbox information
        dialogs = []
        for idx, msg in enumerate(context.conversation):
            # Try to find matching bubble for this message
            bbox = [0.0, 0.0, 0.0, 0.0]  # Default if not found
            
            if idx < len(bubbles):
                bubble = bubbles[idx]
                bbox_data = bubble.get("bbox", {})
                
                # Extract bbox coordinates and ensure correct min/max order
                x1_raw = float(bbox_data.get("x1", 0))
                y1_raw = float(bbox_data.get("y1", 0))
                x2_raw = float(bbox_data.get("x2", 0))
                y2_raw = float(bbox_data.get("y2", 0))
                
                # Ensure x1 <= x2 and y1 <= y2
                x1 = min(x1_raw, x2_raw)
                x2 = max(x1_raw, x2_raw)
                y1 = min(y1_raw, y2_raw)
                y2 = max(y1_raw, y2_raw)
                
                # Normalize coordinates if they are in pixel format
                # (merge_step v3.0 returns pixel coordinates)
                if x1 > 1.0 or y1 > 1.0 or x2 > 1.0 or y2 > 1.0:
                    # Coordinates are in pixels, normalize to 0-1
                    x1_norm = x1 / image_width if image_width > 0 else 0.0
                    y1_norm = y1 / image_height if image_height > 0 else 0.0
                    x2_norm = x2 / image_width if image_width > 0 else 0.0
                    y2_norm = y2 / image_height if image_height > 0 else 0.0
                    bbox = [x1_norm, y1_norm, x2_norm, y2_norm]
                else:
                    # Already normalized
                    bbox = [x1, y1, x2, y2]
            
            dialog_item = DialogItem(
                position=bbox,
                text=msg.content,
                speaker=msg.speaker,
                from_user=(msg.speaker == "user"),
            )
            logger.info(f"[{__name__}:get_merge_step_analysis_result:L{735}] Dialog text: {msg.content}")
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
        
        # Validate that dialogs were extracted
        if not dialogs or len(dialogs) == 0:
            logger.error(f"No dialogs extracted from image: {content_url}")
            raise HTTPException(
                status_code=400,
                detail="No dialogs found in the image. Please ensure the image contains chat messages.",
            )
        
        logger.info(f"merge_step analysis completed for {content_url}: {len(dialogs)} dialogs extracted")
        
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
            # Requirement 9.2: Format dialogs as conversation history
            conversation = []
            for dialog_item in dialog:
                conversation.append({
                    "speaker": dialog_item.speaker if dialog_item.speaker in ["user", "unknown", "self"] else "talker",
                    "text": dialog_item.text,
                })
            
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


def _find_last_talker_message(dialogs: list[DialogItem]) -> str:
    """
    从 dialogs 中找到 talker 或 left 的最后一句话。
    
    Args:
        dialogs: DialogItem 列表
    
    Returns:
        talker/left 的最后一句话
        
    Raises:
        HTTPException: 如果没有找到 talker/left 消息
    """
    for dialog_item in reversed(dialogs):
        speaker = dialog_item.speaker.lower().strip()
        text = dialog_item.text.strip()
        
        # 检查是否为 talker 或 left
        if speaker in ("talker", "left") and text:
            logger.info(f"Found talker/left message: {text[:50]}...")
            return text
    
    # 没找到 talker/left 消息，抛出异常
    logger.error("No talker/left message found in dialogs")
    raise HTTPException(
        status_code=400,
        detail="No talker message found in the image. The image must contain at least one message from the chat partner."
    )


async def _generate_reply(
    request: PredictRequest,
    orchestrator: OrchestratorDep,
    analysis_queue: List[ImageAnalysisQueueInput],
    last_content_type: Literal["image", "text"],  # 新增
    last_content_value: str,  # 新增
) -> List[str]:
    try:
        logger.info("="*60)
        logger.info("Reply generation requested, calling Orchestrator")
        logger.info(f"Last content type: {last_content_type}")
        logger.info(f"Last content value: {last_content_value[:100]}...")
        logger.info("="*60)
        suggested_replies: list[str] = []
        
        for resource_index, (resources, dialog, list_image_result) in enumerate(analysis_queue):
            # Requirement 9.2: Format dialogs as conversation history
            conversation = []
            for dialog_item in dialog:
                conversation.append({
                    "speaker": dialog_item.speaker,
                    "text": dialog_item.text,
                })
            
            # 新增：根据最后一个 content 的类型选择 reply_sentence
            reply_sentence = ""
            if resource_index == len(analysis_queue) - 1:  # 只在最后一个组处理
                logger.info("-"*60)
                logger.info("Selecting reply_sentence (Last Message):")
                logger.info(f"  - Last content type: {last_content_type}")
                
                if last_content_type == "text":
                    # 文字：直接使用文字内容
                    reply_sentence = last_content_value
                    logger.info(f"  - Strategy: Using text content directly")
                    logger.info(f"  - Reply sentence: '{reply_sentence}'")
                else:  # image
                    # 图片：找最后一个图片的 talker/left 消息
                    logger.info(f"  - Strategy: Finding talker/left message from image")
                    
                    # 从 list_image_result 中找最后一个图片类型的 result
                    last_image_result = None
                    for result in reversed(list_image_result):
                        # 检查 result.content 是否为 URL（图片）
                        if _is_url(result.content):
                            last_image_result = result
                            logger.info(f"  - Found last image: {result.content}")
                            break
                    
                    if last_image_result:
                        # 使用最后一个图片的 dialogs
                        logger.info(f"  - Searching in {len(last_image_result.dialogs)} dialogs from last image")
                        reply_sentence = _find_last_talker_message(last_image_result.dialogs)
                        logger.info(f"  - Reply sentence: '{reply_sentence}'")
                    else:
                        # 没有找到图片类型的 result，使用所有 dialogs（后备方案）
                        logger.info(f"  - No image result found, using all dialogs (fallback)")
                        logger.info(f"  - Searching in {len(dialog)} dialogs")
                        reply_sentence = _find_last_talker_message(dialog)
                        logger.info(f"  - Reply sentence: '{reply_sentence}'")
                
                logger.info("-"*60)
            
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
                    persona=request.other_properties.lower() if request.other_properties else "",
                    scene=request.scene,
                    reply_sentence=reply_sentence,  # 新增
                )
                
                # 打印传递给 orchestrator 的 reply_sentence
                if reply_sentence:
                    logger.info(f"Passing reply_sentence to orchestrator: '{reply_sentence}'")
                
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
                            # Support multiple JSON formats:
                            # 1. Standard format: {"replies": [{"text": "..."}, ...]}
                            # 2. Short format: {"r": [["text", null], ...], "adv": "..."}
                            
                            if "replies" in reply_text:
                                # Standard format
                                suggested_reply_items = reply_text.get("replies", [])
                                suggested_replies = [item.get("text", "") for item in suggested_reply_items]
                            elif "r" in reply_text:
                                # Short format: "r" contains array of [text, null] pairs
                                r_items = reply_text.get("r", [])
                                suggested_replies = []
                                for item in r_items:
                                    if isinstance(item, list) and len(item) > 0:
                                        # Extract first element (text)
                                        suggested_replies.append(str(item[0]) if item[0] else "")
                                    elif isinstance(item, str):
                                        # Direct string
                                        suggested_replies.append(item)
                                logger.info(f"Parsed {len(suggested_replies)} replies from 'r' format")
                            else:
                                logger.warning(f"Unknown JSON format, no 'replies' or 'r' field found: {list(reply_text.keys())}")
                                suggested_replies = []
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
    # Log handle_image start with trace
    if trace_logger.should_log_timing():
        trace_logger.log_event({
            "level": "debug",
            "type": "handle_image_start",
            "session_id": request.session_id,
            "user_id": request.user_id,
            "content_count": len(request.content),
            "elapsed_ms": int((time.time() - start_time) * 1000),
        })
    
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
            
            if trace_logger.should_log_timing():
                logger.info(f"Screenshot analysis completed in {screenshot_duration_ms}ms for {content_url}")
            
            image_result.content = content_url
            logger.info(f"Image result: {type(image_result)}")
            logger.info(f"Content processed successfully: {len(image_result.dialogs)} dialogs extracted")
            
            # Validate that dialogs were extracted
            if not image_result.dialogs or len(image_result.dialogs) == 0:
                logger.error(f"No dialogs extracted from image: {content_url}")
                raise HTTPException(
                    status_code=400,
                    detail="No dialogs found in the image. Please ensure the image contains chat messages.",
                )
     
            # Add metadata for consistency with merge_step cache
            image_result_data = image_result.model_dump(mode="json")
            image_result_data["_model"] = "non-merge-step"
            image_result_data["_strategy"] = "traditional"
            
            await cache_service.append_event(
                session_id=request.session_id,
                category="image_result",
                resource=content_url,
                payload=image_result_data,
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
                
                raise HTTPException(
                    status_code=400,
                    detail=f"Load image failed: {str(e)}",
                )
            
            else:
                # Requirement 7.3: Handle inference errors (HTTP 500)
                logger.error(f"Inference failed for {content_url}: {e}", exc_info=True)
                metrics.record_request("predict", 500, int((time.time() - start_time) * 1000))
                
                raise HTTPException(
                    status_code=500,
                    detail=f"Inference error: {str(e)}",
                )

    # If merge_step is enabled and we have results, return them directly
    if use_merge_step and items:
        # Extract results from items
        results = [item_result for _, _, item_result in items]
        logger.info(f"[{__name__}:predict:L{1196}] Merge step results: {results}")
        
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
            
            # 新增：获取最后一个 content 的类型和值
            last_content_type = items[-1][0] if items else "text"
            last_content_value = items[-1][1] if items else ""
            
            reply_start = time.time()
            suggested_replies = await _generate_reply(
                request,
                orchestrator,
                analysis_queue,
                last_content_type,  # 新增
                last_content_value,  # 新增
            )
            reply_duration_ms = int((time.time() - reply_start) * 1000)
            
            if trace_logger.should_log_timing():
                trace_logger.log_event({
                    "level": "debug",
                    "type": "reply_generation",
                    "session_id": request.session_id,
                    "duration_ms": reply_duration_ms,
                    "reply_count": len(suggested_replies),
                })
                logger.info(f"Reply generation completed in {reply_duration_ms}ms")
        
        # Record successful request
        duration_ms = int((time.time() - start_time) * 1000)
        metrics.record_request("predict", 200, duration_ms)
        
        if trace_logger.should_log_timing():
            trace_logger.log_event({
                "level": "debug",
                "type": "handle_image_complete",
                "session_id": request.session_id,
                "flow": "merge_step",
                "total_duration_ms": duration_ms,
            })
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
        
        if trace_logger.should_log_timing():
            trace_logger.log_event({
                "level": "debug",
                "type": "scenario_analysis",
                "session_id": request.session_id,
                "duration_ms": scenario_duration_ms,
                "result_count": len(results),
            })
            logger.info(f"Merged scenario analysis completed in {scenario_duration_ms}ms")
    
    suggested_replies: list[str] = []
    # Step 4: Generate replies if requested
    if request.reply and items:
        # 新增：获取最后一个 content 的类型和值
        last_content_type = items[-1][0] if items else "text"
        last_content_value = items[-1][1] if items else ""
        
        reply_start = time.time()
        suggested_replies = await _generate_reply(
            request,
            orchestrator,
            analysis_queue,
            last_content_type,  # 新增
            last_content_value,  # 新增
        )
        reply_duration_ms = int((time.time() - reply_start) * 1000)
        
        if trace_logger.should_log_timing():
            trace_logger.log_event({
                "level": "debug",
                "type": "reply_generation",
                "session_id": request.session_id,
                "duration_ms": reply_duration_ms,
                "reply_count": len(suggested_replies),
            })
            logger.info(f"Reply generation completed in {reply_duration_ms}ms")

    # Record successful request
    duration_ms = int((time.time() - start_time) * 1000)
    metrics.record_request("predict", 200, duration_ms)
    
    if trace_logger.should_log_timing():
        trace_logger.log_event({
            "level": "debug",
            "type": "handle_image_complete",
            "session_id": request.session_id,
            "flow": "traditional",
            "total_duration_ms": duration_ms,
        })
    
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
    # Log text QA start with trace
    if trace_logger.should_log_timing():
        trace_logger.log_event({
            "level": "debug",
            "type": "text_qa_start",
            "session_id": request.session_id,
            "user_id": request.user_id,
            "elapsed_ms": int((time.time() - start_time) * 1000),
        })
    
    step_start = time.time()
    question = "\n".join([c.strip() for c in request.content if c and c.strip()])
    
    if trace_logger.should_log_timing():
        trace_logger.log_event({
            "level": "debug",
            "type": "question_parsing",
            "session_id": request.session_id,
            "duration_ms": int((time.time() - step_start) * 1000),
            "elapsed_ms": int((time.time() - start_time) * 1000),
        })
    
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

    step_start = time.time()
    if request.language == "zh":
        prompt = f"请用中文回答用户问题。\n\n用户问题：\n{question}\n"
    else:
        prompt = f"Answer the user's question clearly and helpfully.\n\nUser question:\n{question}\n"
    
    if trace_logger.should_log_timing():
        trace_logger.log_event({
            "level": "debug",
            "type": "prompt_building",
            "session_id": request.session_id,
            "duration_ms": int((time.time() - step_start) * 1000),
            "elapsed_ms": int((time.time() - start_time) * 1000),
        })

    try:
        step_start = time.time()
        llm_adapter = create_llm_adapter()
        
        if trace_logger.should_log_timing():
            trace_logger.log_event({
                "level": "debug",
                "type": "create_llm_adapter",
                "session_id": request.session_id,
                "duration_ms": int((time.time() - step_start) * 1000),
                "elapsed_ms": int((time.time() - start_time) * 1000),
            })
        
        step_start = time.time()
        
        if trace_logger.should_log_timing():
            trace_logger.log_event({
                "level": "debug",
                "type": "llm_call_start",
                "session_id": request.session_id,
                "task_type": "text_qa",
                "elapsed_ms": int((time.time() - start_time) * 1000),
            })
        
        llm_result = await llm_adapter.call(
            LLMCall(
                task_type="generation",
                prompt=prompt,
                quality="normal",
                user_id=request.user_id,
            )
        )
        
        if trace_logger.should_log_timing():
            trace_logger.log_event({
                "level": "debug",
                "type": "llm_call_end",
                "session_id": request.session_id,
                "task_type": "text_qa",
                "duration_ms": int((time.time() - step_start) * 1000),
                "elapsed_ms": int((time.time() - start_time) * 1000),
            })

        step_start = time.time()
        duration_ms = int((time.time() - start_time) * 1000)
        metrics.record_request("predict", 200, duration_ms)
        
        if trace_logger.should_log_timing():
            trace_logger.log_event({
                "level": "debug",
                "type": "metrics_recording",
                "session_id": request.session_id,
                "duration_ms": int((time.time() - step_start) * 1000),
            })
        
        step_start = time.time()
        response = PredictResponse(
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
        
        if trace_logger.should_log_timing():
            trace_logger.log_event({
                "level": "debug",
                "type": "response_building",
                "session_id": request.session_id,
                "duration_ms": int((time.time() - step_start) * 1000),
            })
            trace_logger.log_event({
                "level": "debug",
                "type": "text_qa_complete",
                "session_id": request.session_id,
                "total_duration_ms": duration_ms,
            })
        
        return response

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