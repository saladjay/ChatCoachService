"""Screenshot parser service for extracting structured conversation data from chat screenshots.

This module provides the main ScreenshotParserService class that orchestrates
the screenshot parsing workflow by coordinating image fetching, prompt building,
LLM invocation, and result normalization.

VERSION: 2.0 - Updated logging to show bubbles instead of messages
"""

import logging
import time
import uuid
from typing import Any

from app.models.screenshot import (
    ParseScreenshotRequest,
    ParseScreenshotResponse,
    ParsedScreenshotData,
    ParseOptions,
    ImageMeta,
)
from app.services.image_fetcher import ImageFetcher
from app.services.llm_adapter import LLMAdapterImpl
from app.services.prompt_manager import PromptManager, PromptType
from app.services.result_normalizer import ResultNormalizer
from app.observability.trace_logger import trace_logger


logger = logging.getLogger(__name__)


class ScreenshotParserService:
    """Service for parsing chat screenshots into structured conversation data.
    
    This service coordinates the complete parsing workflow:
    1. Download and validate the image
    2. Build prompts for the multimodal LLM
    3. Invoke the LLM with the image and prompts
    4. Validate and normalize the LLM output
    5. Return standardized response
    
    Error codes:
    - 0: Success
    - 1001: Image download/processing failure
    - 1002: LLM call failure
    - 1003: Invalid JSON response from LLM
    - 1004: Missing required fields in LLM output
    """

    # Low confidence threshold for marking bubbles for review
    LOW_CONFIDENCE_THRESHOLD = 0.3

    def __init__(
        self,
        image_fetcher: ImageFetcher,
        prompt_manager: PromptManager,
        llm_adapter: LLMAdapterImpl,
        result_normalizer: ResultNormalizer,
    ):
        """Initialize the screenshot parser service.
        
        Args:
            image_fetcher: Component for downloading and processing images
            prompt_manager: Prompt version manager for loading active prompts
            llm_adapter: LLM adapter for calling multimodal LLM APIs
            result_normalizer: Component for validating and normalizing output
        """
        self.image_fetcher = image_fetcher
        self.prompt_manager = prompt_manager
        self.llm_adapter = llm_adapter
        self.result_normalizer = result_normalizer

    def _log_merge_step_conversation(
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
            parsed_json: Parsed JSON response
        """
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
            screenshot_parse = parsed_json.get("screenshot_parse", {})
            layout = screenshot_parse.get("layout", {})
            left_role = layout.get("left_role", "unknown")
            right_role = layout.get("right_role", "unknown")
            
            # Log bubble details with layout context
            logger.info(
                f"[{session_id}] 🏁 RACE [{strategy}|{model}] Layout: left={left_role}, right={right_role}"
            )
            logger.info(
                f"[{session_id}] 🏁 RACE [{strategy}|{model}] Extracted {len(sorted_bubbles)} bubbles (sorted top→bottom):"
            )
            
            for idx, bubble in enumerate(sorted_bubbles, 1):
                sender = bubble.get("sender", "unknown")
                text = bubble.get("text", "")
                column = bubble.get("column", "unknown")
                bbox = bubble.get("bbox", {})
                x1 = bbox.get("x1", 0)
                y1 = bbox.get("y1", 0)
                x2 = bbox.get("x2", 0)
                y2 = bbox.get("y2", 0)
                
                # Show expected role based on layout
                expected_role = left_role if column == "left" else right_role
                role_match = "✓" if sender == expected_role else "✗"
                
                # Truncate long messages for readability
                display_text = text[:100] + "..." if len(text) > 100 else text
                
                logger.info(
                    f"[{session_id}] 🏁   [{idx}] {sender}({column}) {role_match} "
                    f"bbox=[{x1},{y1},{x2},{y2}]: {display_text}"
                )
                
        except Exception as e:
            logger.warning(f"[{session_id}] Failed to log merge_step conversation: {e}", exc_info=True)

    def _log_screenshot_dialogs(
        self,
        session_id: str,
        strategy: str,
        model: str,
        parsed_json: dict
    ) -> None:
        """Log extracted dialogs from screenshot parsing.
        
        Args:
            session_id: Session ID for logging
            strategy: Strategy name (multimodal/premium)
            model: Model name
            parsed_json: Parsed JSON response
        """
        try:
            dialogs = parsed_json.get("dialogs", [])
            participants = parsed_json.get("participants", {})
            
            # Log participants info
            user_nickname = participants.get("user", {}).get("nickname", "Unknown")
            target_nickname = participants.get("target", {}).get("nickname", "Unknown")
            
            logger.info(
                f"[{session_id}] screenshot_parse [{strategy}|{model}] Participants: "
                f"User='{user_nickname}', Target='{target_nickname}'"
            )
            
            # Log dialog details
            logger.info(
                f"[{session_id}] screenshot_parse [{strategy}|{model}] Extracted {len(dialogs)} dialogs:"
            )
            
            for idx, dialog in enumerate(dialogs, 1):
                speaker = dialog.get("speaker", "unknown")
                text = dialog.get("text", "")
                position = dialog.get("position", "unknown")
                
                # Truncate long messages for readability
                display_text = text[:100] + "..." if len(text) > 100 else text
                
                logger.info(
                    f"[{session_id}]   [{idx}] {speaker} ({position}): {display_text}"
                )
                
        except Exception as e:
            logger.warning(f"[{session_id}] Failed to log screenshot dialogs: {e}")

    async def _race_multimodal_calls(
        self,
        prompt: str,
        image_data: str,
        image_type: str,
        mime_type: str,
        user_id: str,
        session_id: str,
        provider: str,
        validator: callable,
        task_name: str = "multimodal_race",
    ) -> tuple[str, Any]:
        """
        Race two multimodal LLM calls and return the first valid result.
        
        This method simultaneously calls:
        1. Default multimodal model (fast, lower quality)
        2. Premium model (slower, higher quality)
        
        And returns whichever completes first with valid data.
        
        Args:
            prompt: Text prompt for LLM
            image_data: Image URL or base64 string
            image_type: "url" or "base64"
            mime_type: Image MIME type (e.g., "image/jpeg")
            user_id: User ID for billing/logging
            session_id: Session ID for logging
            provider: Provider name (e.g., "openrouter")
            validator: Function to validate parsed JSON result
            task_name: Name for logging (e.g., "screenshot_parse")
            
        Returns:
            Tuple of (winning_strategy, llm_result)
            
        Raises:
            ValueError: If both calls fail or return invalid data
        """
        import asyncio
        
        # Define async function for multimodal call
        async def call_multimodal_llm():
            step_id = uuid.uuid4().hex
            start_time = time.time()
            
            trace_logger.log_event({
                "level": "debug",
                "type": "step_start",
                "step_id": step_id,
                "step_name": f"{task_name}_multimodal",
                "task_type": task_name,
                "session_id": session_id,
                "user_id": user_id,
            })
            
            try:
                result = await self.llm_adapter.call_multimodal(
                    prompt=prompt,
                    image_data=image_data,
                    image_type=image_type,
                    mime_type=mime_type,
                    user_id=user_id,
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                trace_logger.log_event({
                    "level": "debug",
                    "type": "step_end",
                    "step_id": step_id,
                    "step_name": f"{task_name}_multimodal",
                    "session_id": session_id,
                    "duration_ms": duration_ms,
                    "provider": result.provider,
                    "model": result.model,
                    "status": "success",
                })
                
                logger.info(
                    f"[{session_id}] {task_name} multimodal completed in {duration_ms}ms "
                    f"(model: {result.model})"
                )
                return ("multimodal", result)
                
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                trace_logger.log_event({
                    "level": "error",
                    "type": "step_end",
                    "step_id": step_id,
                    "step_name": f"{task_name}_multimodal",
                    "session_id": session_id,
                    "duration_ms": duration_ms,
                    "status": "error",
                    "error": str(e),
                })
                logger.warning(f"[{session_id}] {task_name} multimodal failed: {e}")
                raise
        
        # Define async function for premium call
        async def call_premium_llm():
            step_id = uuid.uuid4().hex
            start_time = time.time()
            
            trace_logger.log_event({
                "level": "debug",
                "type": "step_start",
                "step_id": step_id,
                "step_name": f"{task_name}_premium",
                "task_type": task_name,
                "session_id": session_id,
                "user_id": user_id,
            })
            
            try:
                result = await self.llm_adapter.call_multimodal(
                    prompt=prompt,
                    image_data=image_data,
                    image_type=image_type,
                    mime_type=mime_type,
                    user_id=user_id,
                    provider=provider,
                    model="google/gemini-2.0-flash-001",
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                trace_logger.log_event({
                    "level": "debug",
                    "type": "step_end",
                    "step_id": step_id,
                    "step_name": f"{task_name}_premium",
                    "session_id": session_id,
                    "duration_ms": duration_ms,
                    "provider": result.provider,
                    "model": result.model,
                    "status": "success",
                })
                
                logger.info(
                    f"[{session_id}] {task_name} premium completed in {duration_ms}ms "
                    f"(model: {result.model})"
                )
                return ("premium", result)
                
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                trace_logger.log_event({
                    "level": "error",
                    "type": "step_end",
                    "step_id": step_id,
                    "step_name": f"{task_name}_premium",
                    "session_id": session_id,
                    "duration_ms": duration_ms,
                    "status": "error",
                    "error": str(e),
                })
                logger.warning(f"[{session_id}] {task_name} premium failed: {e}")
                raise
        
        # Start both tasks simultaneously
        logger.info(f"[{session_id}] Starting {task_name} race: multimodal vs premium")
        multimodal_task = asyncio.create_task(call_multimodal_llm())
        premium_task = asyncio.create_task(call_premium_llm())
        
        llm_result = None
        winning_strategy = None
        all_results = []  # Store all completed results
        
        # Get debug settings
        from app.core.config import settings
        wait_for_all = settings.debug_config.race_wait_all
        log_race = settings.debug_config.log_race_strategy
        
        try:
            pending = {multimodal_task, premium_task}
            
            # Wait for all tasks or just first valid one based on debug setting
            while pending:
                # If we already have a winner and not in debug mode, cancel remaining
                if llm_result is not None and not wait_for_all:
                    if log_race:
                        logger.info(f"[{session_id}] {task_name}: Winner found, cancelling remaining tasks")
                    break
                
                done, pending = await asyncio.wait(
                    pending,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in done:
                    try:
                        strategy, result = await task
                        
                        import json
                        from app.api.v1.predict import parse_json_with_markdown
                        
                        try:
                            parsed_json = parse_json_with_markdown(result.text)
                            
                            # Log the response for debugging
                            if log_race:
                                logger.info(
                                    f"[{session_id}] {task_name}: {strategy} returned JSON with keys: "
                                    f"{list(parsed_json.keys()) if isinstance(parsed_json, dict) else type(parsed_json)}"
                                )
                            
                            # Log extracted data based on debug settings
                            if task_name == "merge_step" and settings.debug_config.log_merge_step_extraction:
                                self._log_merge_step_conversation(
                                    session_id=session_id,
                                    strategy=strategy,
                                    model=result.model,
                                    parsed_json=parsed_json
                                )
                            elif task_name == "screenshot_parse" and settings.debug_config.log_screenshot_parse:
                                self._log_screenshot_dialogs(
                                    session_id=session_id,
                                    strategy=strategy,
                                    model=result.model,
                                    parsed_json=parsed_json
                                )
                            
                            # Check if valid and store
                            is_valid = validator(parsed_json)
                            all_results.append((strategy, result, is_valid))
                            
                            # If this is the first valid result, mark it as winner
                            if is_valid and llm_result is None:
                                llm_result = result
                                winning_strategy = strategy
                                if log_race:
                                    logger.info(f"[{session_id}] {task_name}: {strategy} won (first valid)")
                            elif is_valid:
                                if log_race:
                                    logger.info(f"[{session_id}] {task_name}: {strategy} also valid (but came second)")
                            else:
                                if log_race:
                                    logger.warning(f"[{session_id}] {task_name}: {strategy} invalid")
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning(
                                f"[{session_id}] {task_name}: {strategy} bad JSON: {e}"
                            )
                    except Exception as e:
                        logger.warning(f"[{session_id}] {task_name}: Task failed: {e}")
            
            # Cancel remaining tasks if not waiting for all
            if not wait_for_all:
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            if llm_result is None:
                raise ValueError(f"Both calls failed for {task_name}")
            
            if log_race:
                logger.info(
                    f"[{session_id}] {task_name} race done: {winning_strategy} won, "
                    f"model={llm_result.model}, total_results={len(all_results)}, "
                    f"wait_all={wait_for_all}"
                )
            
            return winning_strategy, llm_result
            
        except Exception as e:
            for task in [multimodal_task, premium_task]:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            raise

    async def parse_screenshot(
        self,
        request: ParseScreenshotRequest,
    ) -> ParseScreenshotResponse:
        """Parse a chat screenshot and extract structured conversation data.
        
        This method orchestrates the complete parsing workflow:
        1. Fetch and validate the image
        2. Build prompts for the LLM
        3. Call the multimodal LLM
        4. Normalize and validate the output
        5. Add metadata and tracking information
        
        Args:
            request: Parse request containing image URL and options
            
        Returns:
            ParseScreenshotResponse with parsed data or error information
        """
        session_id = request.session_id or "unknown"
        
        # Use default options if not provided
        options = request.options or ParseOptions()
        
        try:
            # Step 1: Fetch and validate image (error code 1001)
            logger.info(
                f"[{session_id}] Fetching image from URL: {request.image_url}"
            )
            
            # Get image format configuration
            from app.core.config import settings
            image_format = settings.llm.multimodal_image_format
            
            try:
                # Fetch image (compress based on configuration)
                # When using URL format, compression is skipped by default
                # When using base64 format, compression depends on LLM_MULTIMODAL_IMAGE_COMPRESS setting
                if image_format == "url":
                    # URL format: Never compress (LLM downloads directly)
                    compress = False
                else:
                    # Base64 format: Use configuration setting
                    compress = settings.llm.multimodal_image_compress
                
                fetched_image = await self.image_fetcher.fetch_image(
                    request.image_url,
                    compress=compress
                )
                logger.info(
                    f"[{session_id}] Image fetched successfully: "
                    f"{fetched_image.width}x{fetched_image.height} "
                    f"({fetched_image.format}), transport format: {image_format}, "
                    f"compressed: {compress}"
                )
            except ValueError as e:
                logger.error(f"[{session_id}] Image fetch failed: {e}")
                return self._create_error_response(
                    code=1001,
                    message=f"Failed to download or process image: {str(e)}",
                    session_id=session_id,
                )
            except Exception as e:
                logger.error(f"[{session_id}] Unexpected image fetch error: {e}")
                return self._create_error_response(
                    code=1001,
                    message=f"Unexpected error fetching image: {str(e)}",
                    session_id=session_id,
                )
            
            # Step 2: Build prompts
            logger.info(f"[{session_id}] Building prompts for LLM")
            prompt = self.prompt_manager.get_active_prompt(PromptType.SCREENSHOT_PARSE)
            if not isinstance(prompt, str) or not prompt.strip():
                return self._create_error_response(
                    code=1002,
                    message="No active screenshot_parse prompt configured",
                    session_id=session_id,
                )
            
            # Step 3: Call multimodal LLM with race strategy (error code 1002, 1003)
            logger.info(f"[{session_id}] Starting LLM race: multimodal vs premium")
            
            llm_start_time = time.time()
            
            # Prepare image data based on configuration
            if image_format == "url":
                image_data = request.image_url
                image_type = "url"
                logger.info(f"[{session_id}] Using URL format for LLM calls")
            else:
                image_data = fetched_image.base64_data
                image_type = "base64"
                logger.info(f"[{session_id}] Using base64 format for LLM calls")
            
            # Define validator for screenshot parse results
            def validate_screenshot_result(parsed_json: dict) -> bool:
                """Check if result has valid dialogs."""
                dialogs = parsed_json.get("dialogs", [])
                is_valid = dialogs and len(dialogs) > 0
                if is_valid:
                    logger.info(f"[{session_id}] Found {len(dialogs)} dialogs")
                return is_valid
            
            try:
                from app.core.config import settings
                
                winning_strategy, llm_result = await self._race_multimodal_calls(
                    prompt=prompt,
                    image_data=image_data,
                    image_type=image_type,
                    mime_type=f"image/{fetched_image.format.lower()}",
                    user_id=session_id,
                    session_id=session_id,
                    provider=settings.llm.default_provider,
                    validator=validate_screenshot_result,
                    task_name="screenshot_parse",
                )
                
                llm_duration_ms = int((time.time() - llm_start_time) * 1000)
                
                logger.info(
                    f"[{session_id}] Race done: {winning_strategy} won in {llm_duration_ms}ms, "
                    f"provider={llm_result.provider}, model={llm_result.model}, "
                    f"tokens={llm_result.input_tokens}+{llm_result.output_tokens}, "
                    f"cost=${llm_result.cost_usd:.4f}"
                )
                
                # Parse JSON from LLM response text (already validated in race)
                import json
                try:
                    parsed_json = json.loads(llm_result.text)
                except json.JSONDecodeError as json_err:
                    # Try to extract JSON from markdown code blocks or other formats
                    parsed_json = self._parse_json_response(llm_result.text)
                
            except ValueError as e:
                # This catches the "Both calls failed" error from race strategy
                llm_duration_ms = int((time.time() - llm_start_time) * 1000)
                error_msg = str(e)
                
                logger.error(f"[{session_id}] LLM race failed: {e}")
                return self._create_error_response(
                    code=1002,
                    message=f"LLM API call failed: {error_msg}",
                    session_id=session_id,
                )
            except RuntimeError as e:
                llm_duration_ms = int((time.time() - llm_start_time) * 1000)
                error_msg = str(e)
                
                # Determine if it's a JSON parsing error (1003) or LLM call error (1002)
                if "parse" in error_msg.lower() or "json" in error_msg.lower():
                    logger.error(f"[{session_id}] JSON parsing failed: {e}")
                    return self._create_error_response(
                        code=1003,
                        message=f"Failed to parse JSON from LLM response: {error_msg}",
                        session_id=session_id,
                    )
                else:
                    logger.error(f"[{session_id}] LLM call failed: {e}")
                    return self._create_error_response(
                        code=1002,
                        message=f"LLM API call failed: {error_msg}",
                        session_id=session_id,
                    )
            except Exception as e:
                llm_duration_ms = int((time.time() - llm_start_time) * 1000)
                
                # Log unexpected error with trace
                trace_logger.log_event({
                    "level": "error",
                    "type": "step_error",
                    "step_id": step_id,
                    "step_name": "screenshot_parse_llm",
                    "task_type": "screenshot_parse",
                    "session_id": session_id,
                    "duration_ms": llm_duration_ms,
                    "error": str(e),
                    "status": "failed",
                })
                
                logger.error(f"[{session_id}] Unexpected LLM error: {e}")
                return self._create_error_response(
                    code=1002,
                    message=f"Unexpected error calling LLM: {str(e)}",
                    session_id=session_id,
                )
            
            # Step 4: Normalize and validate output (error code 1004)
            logger.info(f"[{session_id}] Normalizing LLM output")
            try:
                image_meta = ImageMeta(
                    width=fetched_image.width,
                    height=fetched_image.height
                )
                logger.info(f"llm response: {parsed_json}")
                parsed_data = self.result_normalizer.normalize(
                    raw_json=parsed_json,
                    image_meta=image_meta,
                    options=options,
                )
                logger.info(
                    f"[{session_id}] Normalization successful: "
                    f"{len(parsed_data.bubbles)} bubbles extracted"
                    f"{parsed_data.bubbles}"
                )
            except ValueError as e:
                logger.error(f"[{session_id}] Normalization failed: {e}")
                return self._create_error_response(
                    code=1004,
                    message=f"Missing or invalid required fields: {str(e)}",
                    session_id=session_id,
                )
            except Exception as e:
                logger.error(f"[{session_id}] Unexpected normalization error: {e}")
                return self._create_error_response(
                    code=1004,
                    message=f"Unexpected error normalizing output: {str(e)}",
                    session_id=session_id,
                )
            
            # Step 5: Mark low confidence bubbles for review
            low_confidence_count = self._mark_low_confidence_bubbles(parsed_data)
            if low_confidence_count > 0:
                logger.warning(
                    f"[{session_id}] {low_confidence_count} bubbles marked for review "
                    f"(confidence < {self.LOW_CONFIDENCE_THRESHOLD})"
                )
            
            # Step 6: Add cost and session tracking metadata
            # Note: Metadata is logged but not included in the response structure
            # as per the current ParseScreenshotResponse model
            logger.info(
                f"[{session_id}] Parse complete - "
                f"Session: {session_id}, "
                f"Provider: {llm_result.provider}, "
                f"Model: {llm_result.model}, "
                f"Input tokens: {llm_result.input_tokens}, "
                f"Output tokens: {llm_result.output_tokens}, "
                f"Cost: ${llm_result.cost_usd:.4f}"
            )
            
            # Return success response
            return ParseScreenshotResponse(
                code=0,
                msg="Success",
                data=parsed_data
            )
            
        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(f"[{session_id}] Unexpected error in parse_screenshot: {e}", exc_info=True)
            return self._create_error_response(
                code=1004,
                message=f"Unexpected error during parsing: {str(e)}",
                session_id=session_id,
            )

    def _create_error_response(
        self,
        code: int,
        message: str,
        session_id: str,
    ) -> ParseScreenshotResponse:
        """Create a standardized error response.
        
        Args:
            code: Error code (1001-1004)
            message: Descriptive error message
            session_id: Session ID for tracking
            
        Returns:
            ParseScreenshotResponse with error information
        """
        logger.error(f"[{session_id}] Error {code}: {message}")
        return ParseScreenshotResponse(
            code=code,
            msg=message,
            data=None
        )

    def _mark_low_confidence_bubbles(
        self,
        parsed_data: ParsedScreenshotData
    ) -> int:
        """Mark bubbles with low confidence for review.
        
        This method identifies bubbles with confidence scores below the threshold
        and logs them for potential fallback processing or manual review.
        
        Args:
            parsed_data: Parsed screenshot data
            
        Returns:
            Number of low confidence bubbles found
        """
        low_confidence_bubbles = [
            bubble for bubble in parsed_data.bubbles
            if bubble.confidence < self.LOW_CONFIDENCE_THRESHOLD
        ]
        
        # Log low confidence bubbles for review
        for bubble in low_confidence_bubbles:
            logger.warning(
                f"Low confidence bubble detected: "
                f"id={bubble.bubble_id}, "
                f"confidence={bubble.confidence:.2f}, "
                f"text='{bubble.text[:50]}...', "
                f"sender={bubble.sender}, "
                f"position=({bubble.center_x}, {bubble.center_y})"
            )
        
        return len(low_confidence_bubbles)

    def _parse_json_response(self, raw_text: str) -> dict:
        """Parse JSON from LLM response text.
        
        Tries multiple strategies to extract valid JSON:
        1. Direct JSON parsing
        2. Extract from markdown code blocks
        3. Extract complete JSON objects using bracket matching
        4. Simple regex pattern matching
        
        Args:
            raw_text: Raw text response from LLM
            
        Returns:
            Parsed JSON dictionary
            
        Raises:
            ValueError: If no valid JSON could be extracted
        """
        import json
        import re
        
        # 1. Try direct JSON parsing
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        # 2. Try extracting from markdown code blocks
        code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        matches = re.findall(code_block_pattern, raw_text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        # 3. Try extracting complete JSON objects using stack matching
        json_objects = self._extract_complete_json_objects(raw_text)
        for json_str in json_objects:
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue

        # 4. Fallback: Try simple regex pattern
        json_pattern = r"\{.*\}"
        matches = re.findall(json_pattern, raw_text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        # All parsing attempts failed
        raise ValueError(f"Could not extract valid JSON from response: {raw_text[:200]}...")

    def _extract_complete_json_objects(self, text: str) -> list[str]:
        """Extract all complete JSON objects from text using stack-based bracket matching.
        
        This method finds properly balanced JSON objects by tracking opening and closing braces.
        
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
