"""API routes for conversation generation.

This module implements the generate reply endpoint that:
- Validates request parameters
- Invokes the Orchestrator for reply generation
- Handles errors and returns appropriate responses

Requirements: 1.1, 1.2, 1.3, 1.4
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.core.dependencies import OrchestratorDep
from app.core.exceptions import (
    OrchestrationError,
    QuotaExceededError,
)
from app.models.api import (
    ErrorResponse,
    GenerateReplyRequest,
    GenerateReplyResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post(
    "/reply",
    response_model=GenerateReplyResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        402: {"model": ErrorResponse, "description": "Quota exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Generate a reply suggestion",
    description="Generate a reply suggestion for a conversation using AI.",
)
async def generate_reply(
    request: GenerateReplyRequest,
    orchestrator: OrchestratorDep,
) -> GenerateReplyResponse:
    """Generate a reply suggestion for a conversation.
    
    This endpoint orchestrates the full generation flow:
    1. Build context from conversation history
    2. Analyze the conversation scene
    3. Infer user persona
    4. Generate reply using LLM
    5. Check reply appropriateness
    
    Args:
        request: The generation request with user/conversation info.
        orchestrator: The orchestrator service (injected).
    
    Returns:
        GenerateReplyResponse with generated reply and metadata.
    
    Raises:
        HTTPException: For validation errors (400), quota exceeded (402),
                      or internal errors (500).
    
    Requirements: 1.1, 1.2, 1.3, 1.4
    """
    try:
        # Call orchestrator to generate reply
        response = await orchestrator.generate_reply(request)
        return response
        
    except QuotaExceededError as e:
        # Quota exceeded - return 402
        logger.warning(f"Quota exceeded for user {request.user_id}: {e}")
        raise HTTPException(
            status_code=402,
            detail={
                "error": "quota_exceeded",
                "message": str(e),
            },
        )
        
    except OrchestrationError as e:
        # Orchestration error - return 500 with friendly message
        logger.error(f"Orchestration error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "An error occurred during generation",
            },
        )
        
    except Exception as e:
        # Unexpected error - log and return 500
        logger.exception(f"Unexpected error in generate_reply: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "An unexpected error occurred",
            },
        )
