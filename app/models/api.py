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




class PredictRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, description="图片 URL 列表")
    app_name: str = Field(..., description="聊天应用名称")
    language: str = Field(..., description="语言代码")
    user_id: str = Field(..., min_length=1, description="用户 ID")
    request_id: Optional[str] = Field(None, description="请求 ID（可选）")
    conf_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="置信度阈值（可选，0.0-1.0）")
    reply: bool = Field(False, description="是否获取建议回复（可选，默认 False）")

    @field_validator("app_name")
    @classmethod
    def validate_app_name(cls, v: str) -> str:
        allowed = get_app_names()
        if v not in allowed:
            raise ValueError(f"app_name must be one of {allowed}")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        allowed = get_languages()
        if v not in allowed:
            raise ValueError(f"language must be one of {allowed}")
        return v


class DialogItem(BaseModel):
    position: list[float]  # [min_x, min_y, max_x, max_y] 屏幕尺寸百分比 (0.0-1.0)
    text: str  # 对话文字内容
    speaker: str  # 发言者，"self" 或 "other"


class ImageResult(BaseModel):
    url: str
    dialogs: list[DialogItem]


class PredictResponse(BaseModel):
    success: bool
    message: str
    user_id: str
    request_id: Optional[str]
    results: list[ImageResult]
    suggested_replies: Optional[list[str]] = None
