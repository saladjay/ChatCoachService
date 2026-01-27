"""Screenshot parser service for extracting structured conversation data from chat screenshots.

This module provides the main ScreenshotParserService class that orchestrates
the screenshot parsing workflow by coordinating image fetching, prompt building,
LLM invocation, and result normalization.
"""

import logging
from typing import Any

from app.models.screenshot import (
    ParseScreenshotRequest,
    ParseScreenshotResponse,
    ParsedScreenshotData,
    ParseOptions,
    ImageMeta,
)
from app.services.image_fetcher import ImageFetcher
from app.services.prompt_builder import PromptBuilder
from app.services.multimodal_llm_adapter import MultimodalLLMClient
from app.services.result_normalizer import ResultNormalizer


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
        prompt_builder: PromptBuilder,
        llm_client: MultimodalLLMClient,
        result_normalizer: ResultNormalizer,
    ):
        """Initialize the screenshot parser service.
        
        Args:
            image_fetcher: Component for downloading and processing images
            prompt_builder: Component for constructing LLM prompts
            llm_client: Component for calling multimodal LLM APIs
            result_normalizer: Component for validating and normalizing output
        """
        self.image_fetcher = image_fetcher
        self.prompt_builder = prompt_builder
        self.llm_client = llm_client
        self.result_normalizer = result_normalizer

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
            try:
                fetched_image = await self.image_fetcher.fetch_image(request.image_url)
                logger.info(
                    f"[{session_id}] Image fetched successfully: "
                    f"{fetched_image.width}x{fetched_image.height} "
                    f"({fetched_image.format})"
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
            system_prompt, user_prompt = self.prompt_builder.build_prompts(options)
            
            # Step 3: Call multimodal LLM (error code 1002, 1003)
            logger.info(f"[{session_id}] Calling multimodal LLM")
            try:
                llm_response = await self.llm_client.call(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    image_base64=fetched_image.base64_data,
                )
                logger.info(
                    f"[{session_id}] LLM call successful: "
                    f"provider={llm_response.provider}, "
                    f"model={llm_response.model}, "
                    f"tokens={llm_response.input_tokens}+{llm_response.output_tokens}, "
                    f"cost=${llm_response.cost_usd:.4f}"
                )
            except RuntimeError as e:
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
                parsed_data = self.result_normalizer.normalize(
                    raw_json=llm_response.parsed_json,
                    image_meta=image_meta,
                    options=options,
                )
                logger.info(
                    f"[{session_id}] Normalization successful: "
                    f"{len(parsed_data.bubbles)} bubbles extracted"
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
                f"Provider: {llm_response.provider}, "
                f"Model: {llm_response.model}, "
                f"Input tokens: {llm_response.input_tokens}, "
                f"Output tokens: {llm_response.output_tokens}, "
                f"Cost: ${llm_response.cost_usd:.4f}"
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
