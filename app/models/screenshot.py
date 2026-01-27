"""Data models for the chat screenshot parser service.

This module defines Pydantic models for:
- ParseScreenshotRequest: Input for the screenshot parsing endpoint
- ParseScreenshotResponse: Output from the screenshot parsing endpoint
- Internal data structures for image processing and LLM interaction
"""

from typing import Literal

from pydantic import BaseModel, Field


# Request Models

class ParseOptions(BaseModel):
    """Optional parameters for customizing screenshot parsing behavior."""

    need_nickname: bool = Field(
        default=True,
        description="Extract participant nicknames from screenshot"
    )
    need_sender: bool = Field(
        default=True,
        description="Determine sender attribution for each bubble"
    )
    force_two_columns: bool = Field(
        default=True,
        description="Assume two-column layout (left/right)"
    )
    app_type: Literal["wechat", "line", "whatsapp", "unknown"] = Field(
        default="unknown",
        description="Chat application type for app-specific parsing hints"
    )


class ParseScreenshotRequest(BaseModel):
    """Request model for the POST /api/v1/chat_screenshot/parse endpoint."""

    image_url: str = Field(
        ...,
        min_length=1,
        description="Public URL of chat screenshot image"
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session ID for request tracking"
    )
    options: ParseOptions | None = Field(
        default=None,
        description="Optional parsing parameters"
    )


# Response Models

class BoundingBox(BaseModel):
    """Rectangular coordinates defining a chat bubble's position."""

    x1: int = Field(..., description="Left x coordinate")
    y1: int = Field(..., description="Top y coordinate")
    x2: int = Field(..., description="Right x coordinate")
    y2: int = Field(..., description="Bottom y coordinate")


class ChatBubble(BaseModel):
    """A single chat message bubble with position and content."""

    bubble_id: str = Field(..., description="Unique identifier within screenshot")
    bbox: BoundingBox = Field(..., description="Bounding box coordinates")
    center_x: int = Field(..., description="Horizontal center point")
    center_y: int = Field(..., description="Vertical center point")
    text: str = Field(..., description="Extracted text content")
    sender: Literal["user", "talker"] = Field(
        ...,
        description="Message sender attribution"
    )
    column: Literal["left", "right"] = Field(
        ...,
        description="Column position in layout"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for extraction accuracy"
    )


class ImageMeta(BaseModel):
    """Metadata about the screenshot image."""

    width: int = Field(..., gt=0, description="Image width in pixels")
    height: int = Field(..., gt=0, description="Image height in pixels")


class Participant(BaseModel):
    """Information about a conversation participant."""

    id: str = Field(..., description="Participant identifier")
    nickname: str = Field(..., description="Participant display name")


class Participants(BaseModel):
    """Information about conversation participants."""

    self: Participant = Field(..., description="Current user (message sender)")
    other: Participant = Field(..., description="Conversation partner")


class LayoutInfo(BaseModel):
    """Information about the chat UI layout."""

    type: str = Field(
        default="two_columns",
        description="Layout type identifier"
    )
    left_role: Literal["user", "talker"] = Field(
        ...,
        description="Role assigned to left column"
    )
    right_role: Literal["user", "talker"] = Field(
        ...,
        description="Role assigned to right column"
    )


class ParsedScreenshotData(BaseModel):
    """Complete structured data extracted from a chat screenshot."""

    image_meta: ImageMeta = Field(..., description="Image dimensions")
    participants: Participants = Field(..., description="Conversation participants")
    bubbles: list[ChatBubble] = Field(..., description="Extracted chat bubbles")
    layout: LayoutInfo = Field(..., description="UI layout information")


class ParseScreenshotResponse(BaseModel):
    """Response model for the POST /api/v1/chat_screenshot/parse endpoint."""

    code: int = Field(..., description="Status code (0=success, non-zero=error)")
    msg: str = Field(..., description="Status message")
    data: ParsedScreenshotData | None = Field(
        default=None,
        description="Parsed screenshot data (null on error)"
    )


# Internal Processing Models

class FetchedImage(BaseModel):
    """Internal model for downloaded and processed image data."""

    url: str = Field(..., description="Original image URL")
    width: int = Field(..., gt=0, description="Image width in pixels")
    height: int = Field(..., gt=0, description="Image height in pixels")
    base64_data: str = Field(..., description="Base64-encoded image data")
    format: str = Field(..., description="Image format (png, jpeg, webp)")


class MultimodalLLMResponse(BaseModel):
    """Internal model for multimodal LLM API response."""

    raw_text: str = Field(..., description="Raw text response from LLM")
    parsed_json: dict = Field(..., description="Parsed JSON structure")
    provider: str = Field(..., description="LLM provider name")
    model: str = Field(..., description="Model identifier")
    input_tokens: int = Field(..., ge=0, description="Input token count")
    output_tokens: int = Field(..., ge=0, description="Output token count")
    cost_usd: float = Field(..., ge=0.0, description="API call cost in USD")
