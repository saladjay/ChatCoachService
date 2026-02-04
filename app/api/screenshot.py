"""API routes for chat screenshot parsing.

This module implements the screenshot parsing endpoint that:
- Validates request parameters
- Invokes the ScreenshotParserService for parsing
- Handles errors and returns appropriate responses

Requirements: 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.core.dependencies import ScreenshotParserDep
from app.models.screenshot import (
    ParseScreenshotRequest,
    ParseScreenshotResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat_screenshot", tags=["screenshot"])


@router.post(
    "/parse",
    response_model=ParseScreenshotResponse,
    responses={
        200: {"model": ParseScreenshotResponse, "description": "Successful parse"},
        400: {"model": ParseScreenshotResponse, "description": "Validation error"},
        500: {"model": ParseScreenshotResponse, "description": "Internal server error"},
    },
    summary="Parse a chat screenshot",
    description=(
        "Parse a chat screenshot image and extract structured conversation data. "
        "Uses multimodal AI vision models to identify chat bubbles, extract text, "
        "determine sender attribution, and recognize participant information."
    ),
)
async def parse_screenshot(
    request: ParseScreenshotRequest,
    parser_service: ScreenshotParserDep,
) -> ParseScreenshotResponse:
    """Parse a chat screenshot and extract structured conversation data.
    
    This endpoint orchestrates the screenshot parsing flow:
    1. Download and validate the image
    2. Build prompts for multimodal LLM
    3. Call vision-capable LLM to extract structure
    4. Validate and normalize the output
    5. Return standardized response
    
    Args:
        request: The parse request with image URL and options.
        parser_service: The screenshot parser service (injected).
    
    Returns:
        ParseScreenshotResponse with parsed data or error information.
        
        Success response (code=0):
        - data.image_meta: Image dimensions
        - data.participants: Conversation participants (self and other)
        - data.bubbles: Array of extracted chat bubbles with text and position
        - data.layout: UI layout information
        
        Error responses (code != 0):
        - 1001: Image download or processing failure
        - 1002: LLM API call failure
        - 1003: Invalid JSON response from LLM
        - 1004: Missing required fields in LLM output
    
    Requirements: 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5
    """
    try:
        # Validate image_url format (handled by Pydantic min_length=1)
        # Validate optional parameters (handled by Pydantic field validators)
        # Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
        
        # Log request details
        logger.info(
            f"Parse screenshot request: url={request.image_url}, "
            f"session_id={request.session_id}, "
            f"options={request.options}"
        )
        
        # Call the parser service
        # Requirements: 1.1, 1.2, 1.3, 1.4
        response = await parser_service.parse_screenshot(request)
        
        # Return the response (success or error)
        return response
    
    except Exception as e:
        # Handle validation errors
        if isinstance(e, PydanticValidationError):
            logger.warning(f"Validation error in parse_screenshot: {e}")
            return ParseScreenshotResponse(
                code=400,
                msg=f"Validation error: {str(e)}",
                data=None
            )
        
        # Handle unexpected errors
        logger.exception(f"Unexpected error in parse_screenshot: {e}")
        return ParseScreenshotResponse(
            code=500,
            msg=f"Internal server error: {str(e)}",
            data=None
        )




