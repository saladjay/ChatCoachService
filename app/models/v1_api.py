"""
API data models for ChatCoach API v1.

This module defines Pydantic models for the v1 API endpoints:
- PredictRequest: Input for screenshot analysis and reply generation
- PredictResponse: Output from predict endpoint
- DialogItem: Structured representation of a chat message
- ImageResult: Analysis result for a single screenshot
- HealthResponse: Service health status
- ErrorResponse: Standard error response
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.core.v1_config import get_v1_config


class PredictRequest(BaseModel):
    """
    Request model for the POST /api/v1/ChatCoach/predict endpoint.
    
    Validates:
    - Requirements 3.2: Accept list of image URLs (minimum 1)
    - Requirements 3.3: Accept app_name parameter
    - Requirements 3.4: Accept language parameter
    - Requirements 3.5: Accept user_id parameter
    - Requirements 3.6: Accept optional request_id parameter
    - Requirements 3.7: Accept optional conf_threshold parameter (0.0-1.0)
    - Requirements 3.8: Accept optional reply parameter (boolean)
    - Requirements 6.1: Validate app_name against supported apps
    - Requirements 6.2: Validate language against supported languages
    - Requirements 6.3: Validate conf_threshold is between 0.0 and 1.0
    - Requirements 6.4: Reject empty urls list
    - Requirements 6.5: Reject empty user_id
    """
    
    content: list[str] = Field(
        ...,
        min_length=1,
        description="图片 URL 和文字列表 (minimum 1 required)"
    )
    language: str = Field(
        ...,
        description="语言代码 (e.g., en, zh, es)"
    )
    scene: int = Field(
        ...,
        description="场景类型: 1=纯图片分析, 2=智能问答, 3=混合图片和文字分析"
    )
    user_id: str = Field(
        ...,
        min_length=1,
        description="用户 ID"
    )
    other_properties: str = Field(
        default="",
        description="其他属性 (JSON 字符串格式)"
    )
    session_id: str = Field(
        ...,
        description="会话 ID，方便日后异步请求处理"
    )
    request_id: Optional[str] = Field(
        None,
        description="请求 ID（可选）"
    )
    conf_threshold: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="置信度阈值（可选，0.0-1.0）"
    )
    reply: bool = Field(
        False,
        description="建议回复获取开关，是否获取建议回复（可选，默认 False）"
    )
    scene_analysis: bool = Field(
        False,
        description="场景分析的获取开关，默认 False，文字内容的场景和图片的场景一致"
    )
    
    @field_validator("other_properties")
    @classmethod
    def validate_other_properties(cls, v: str) -> str:
        """
        验证 other_properties 是否为有效的 JSON 字符串
        """
        import json
        
        # 如果为空字符串，直接返回
        if not v or v.strip() == "":
            return ""
        
        try:
            # 尝试解析 JSON
            parsed_json = json.loads(v)
            
            # 重新编码为字符串，确保格式一致
            return json.dumps(parsed_json, ensure_ascii=False, separators=(',', ':'))
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in other_properties: {e.msg} at line {e.lineno} column {e.colno}")
        except Exception as e:
            raise ValueError(f"Validation failed for other_properties: {str(e)}")
    
    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """
        Validate language against supported languages.
        
        Validates: Requirements 6.2
        """
        config = get_v1_config()
        allowed = config.screenshot.supported_languages
        if v not in allowed:
            raise ValueError(
                f"language must be one of {allowed}, got '{v}'"
            )
        return v


class DialogItem(BaseModel):
    """
    Structured representation of a single chat message.
    
    Validates:
    - Requirements 8.2: Position as [min_x, min_y, max_x, max_y] in percentages
    - Requirements 8.3: Text field with message content
    - Requirements 8.4: Speaker field identifying message sender
    - Requirements 8.5: from_user boolean field
    - Requirements 4.8: Normalized coordinates (0.0-1.0)
    """
    
    position: list[float] = Field(
        ...,
        description="Bounding box as [min_x, min_y, max_x, max_y] in percentage coordinates (0.0-1.0)"
    )
    text: str = Field(
        ...,
        description="Message text content"
    )
    speaker: str = Field(
        ...,
        description="Message sender identifier ('self' or speaker name)"
    )
    from_user: bool = Field(
        ...,
        description="Whether the message is from the user (True) or other party (False)"
    )
    
    @field_validator("position")
    @classmethod
    def validate_position(cls, v: list[float]) -> list[float]:
        """
        Validate position coordinates are in correct format and range.
        
        Validates: Requirements 4.8, 8.2
        """
        if len(v) != 4:
            raise ValueError(
                f"position must have exactly 4 values [min_x, min_y, max_x, max_y], got {len(v)}"
            )
        
        min_x, min_y, max_x, max_y = v
        
        # Check all values are in [0.0, 1.0] range
        for i, coord in enumerate(v):
            if not (0.0 <= coord <= 1.0):
                coord_names = ["min_x", "min_y", "max_x", "max_y"]
                raise ValueError(
                    f"position[{i}] ({coord_names[i]}) must be in range [0.0, 1.0], got {coord}"
                )
        
        # Check min <= max for both x and y
        if min_x > max_x:
            raise ValueError(
                f"position min_x ({min_x}) must be <= max_x ({max_x})"
            )
        if min_y > max_y:
            raise ValueError(
                f"position min_y ({min_y}) must be <= max_y ({max_y})"
            )
        
        return v


class ImageResult(BaseModel):
    """
    Analysis result for a single screenshot image.
    
    Validates:
    - Requirements 8.6: content field with original image URL
    - Requirements 8.7: dialogs array with extracted messages
    """
    
    content: str = Field(
        ...,
        description="原始图片 URL 或内容"
    )
    dialogs: list[DialogItem] = Field(
        ...,
        description="提取的对话消息列表"
    )
    scenario: str = Field(
        default="",
        description="场景描述"
    )


class PredictResponse(BaseModel):
    """
    Response model for the POST /api/v1/ChatCoach/predict endpoint.
    
    Validates:
    - Requirements 8.1: Response with success, message, user_id, request_id, results
    - Requirements 3.10: Return structured results
    - Requirements 3.11: Include suggested_replies when reply is requested
    """
    
    success: bool = Field(
        ...,
        description="请求是否成功"
    )
    message: str = Field(
        ...,
        description="状态消息或错误描述"
    )
    user_id: str = Field(
        ...,
        description="用户 ID"
    )
    request_id: Optional[str] = Field(
        None,
        description="请求跟踪 ID"
    )
    session_id: str = Field(
        ...,
        description="会话 ID"
    )
    scene: int = Field(
        ...,
        description="场景类型"
    )
    results: list[ImageResult] = Field(
        ...,
        description="每张图片的分析结果"
    )
    suggested_replies: Optional[list[str]] = Field(
        default=None,
        description="生成的回复建议（仅当 reply=True 时存在）"
    )
    

class HealthResponse(BaseModel):
    """
    Response model for the GET /api/v1/ChatCoach/health endpoint.
    
    Validates:
    - Requirements 2.1: Return service status, timestamp, and version
    - Requirements 2.4: Return HealthResponse model with required fields
    - Requirements 2.5: Check availability of detection and recognition models
    """
    
    status: str = Field(
        ...,
        description="Service health status ('healthy' or 'unhealthy')"
    )
    timestamp: datetime = Field(
        ...,
        description="Current server timestamp"
    )
    version: str = Field(
        ...,
        description="API version"
    )
    models: dict[str, bool] = Field(
        ...,
        description="Model availability status (text_detection, layout_detection, text_recognition)"
    )


class ErrorResponse(BaseModel):
    """
    Standard error response model for all endpoints.
    
    Validates:
    - Requirements 6.6: Return descriptive error messages
    - Requirements 7.1, 7.2, 7.3, 7.4: Consistent error response format
    """
    
    detail: str = Field(
        ...,
        description="Error message describing what went wrong"
    )
