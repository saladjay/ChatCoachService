"""
Middleware for ChatCoach API v1.

This module provides middleware for request/response logging and metrics tracking.

Requirements: 10.3, 10.4, 5.4
"""

import logging
import time
import json
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses.
    
    Logs:
    - Request method, path, query parameters
    - Request headers (excluding sensitive data)
    - Response status code
    - Request duration
    
    Requirements: 10.3, 10.4
    """
    
    def __init__(self, app: ASGIApp):
        """Initialize the middleware."""
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and log details.
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware or endpoint handler
        
        Returns:
            The HTTP response
        """
        # Generate request ID if not present
        request_id = request.headers.get("X-Request-ID", f"req-{int(time.time() * 1000)}")
        
        # Start timing
        start_time = time.time()
        
        # Log incoming request
        logger.info(
            "Incoming request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            
            # Re-raise the exception
            raise


class StructuredLogFormatter(logging.Formatter):
    """
    Custom log formatter that outputs structured JSON logs.
    
    Converts log records to JSON format for easier parsing and analysis.
    
    Requirements: 10.3
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as JSON.
        
        Args:
            record: The log record to format
        
        Returns:
            JSON-formatted log string
        """
        # Build base log entry
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "client_host"):
            log_entry["client_host"] = record.client_host
        if hasattr(record, "user_agent"):
            log_entry["user_agent"] = record.user_agent
        if hasattr(record, "query_params"):
            log_entry["query_params"] = record.query_params
        if hasattr(record, "error"):
            log_entry["error"] = record.error
        if hasattr(record, "error_type"):
            log_entry["error_type"] = record.error_type
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add stack info if present
        if record.stack_info:
            log_entry["stack_info"] = record.stack_info
        
        return json.dumps(log_entry)


def setup_structured_logging(
    level: int = logging.INFO,
    use_json: bool = False
) -> None:
    """
    Set up structured logging for the application.
    
    Args:
        level: Logging level (default: INFO)
        use_json: Whether to use JSON formatting (default: False)
    
    Requirements: 10.3
    """
    # Get root logger
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # Set formatter
    if use_json:
        formatter = StructuredLogFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    console_handler.setFormatter(formatter)
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    root_logger.setLevel(level)
    
    logger.info(f"Structured logging configured: level={logging.getLevelName(level)}, json={use_json}")
