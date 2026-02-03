"""API request and response models for the conversation generation service.

This module defines Pydantic models for:
- GenerateReplyRequest: Input for the generate reply endpoint
- GenerateReplyResponse: Output from the generate reply endpoint
"""

from typing import Literal, List, Dict, Any, Optional

from pydantic import BaseModel, Field, field_validator


# Helper functions for validation - these will be imported from config
def get_app_names() -> list[str]:
    """Get supported app names from configuration."""
    # This is a placeholder - will be replaced with actual config import
    return ["whatsapp", "telegram", "discord", "wechat"]


def get_languages() -> list[str]:
    """Get supported languages from configuration."""
    # This is a placeholder - will be replaced with actual config import
    return ["en", "zh", "es", "ar", "pt"]


class GenerateReplyRequest(BaseModel):
    """Request model for the POST /api/v1/generate/reply endpoint."""

    user_id: str = Field(..., min_length=1, description="User identifier")
    target_id: str = Field(..., min_length=1, description="Target user identifier")
    conversation_id: str = Field(..., min_length=1, description="Conversation identifier")
    resource: Optional[str] = Field(
        default=None, description="Resource identifier (image_url or text content)"
    )
    resources: Optional[List[str]] = Field(
        default=None, description="Resources identifier (image_url or text content)"
    )
    language: str = Field(default="en", description="Language code (en/ar/pt/es/zh-CN)")
    quality: Literal["cheap", "normal", "premium"] = Field(
        default="normal", description="Quality tier for LLM selection"
    )
    force_regenerate: bool = Field(
        default=False, description="Force regeneration even if cached"
    )
    dialogs: List[Dict[str, Any]] = Field(default=[], description="dialogs from screenshot")
    intimacy_value: int = Field(default=50, ge=0, le=100, description="the intimacy of user's setting")
    persona: str = Field(default="", description="user's persona")
    scene: int = Field(default=1, ge=1, le=3, description="scene")


class GenerateReplyResponse(BaseModel):
    """Response model for the POST /api/v1/generate/reply endpoint."""

    reply_text: str = Field(..., description="Generated reply text")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score from 0 to 1"
    )
    intimacy_level_before: int = Field(
        ..., ge=1, le=5, description="Intimacy level before generation"
    )
    intimacy_level_after: int = Field(
        ..., ge=1, le=5, description="Intimacy level after generation"
    )
    model: str = Field(..., description="LLM model used")
    provider: str = Field(..., description="LLM provider used")
    cost_usd: float = Field(..., ge=0.0, description="Total cost in USD")
    fallback: bool = Field(
        default=False, description="Whether fallback response was used"
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str = Field(..., description="Error type identifier")
    message: str = Field(..., description="Human-readable error message")
    details: list[str] | None = Field(
        default=None, description="Additional error details"
    )


