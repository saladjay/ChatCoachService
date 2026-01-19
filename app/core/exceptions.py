"""
Custom exceptions for the application.

This module defines a hierarchy of custom exceptions for error handling:
- AppException: Base exception for all application errors
- ValidationError: Request validation failures (400)
- QuotaExceededError: User quota exceeded (402)
- ServiceTimeoutError: Service call timeout (504)
- ServiceUnavailableError: Service unavailable (503)
- ContextBuildError: Context building failure (500)
- OrchestrationError: General orchestration failure (500)
- FallbackTriggeredError: Fallback response triggered (200 with fallback flag)

Requirements: 4.5
"""

import logging
from typing import Any


logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base exception for application errors.
    
    All custom exceptions should inherit from this class.
    Provides consistent error structure with error_code, message, and details.
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "internal_error",
        details: Any = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details
        super().__init__(message)
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON response."""
        result = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.details is not None:
            result["details"] = self.details
        return result


class ValidationError(AppException):
    """Raised when request validation fails.
    
    HTTP Status: 400 Bad Request
    """
    
    def __init__(self, message: str, details: Any = None):
        super().__init__(
            message=message,
            error_code="validation_error",
            details=details,
        )


class QuotaExceededError(AppException):
    """Raised when user quota is exceeded.
    
    HTTP Status: 402 Payment Required
    """
    
    def __init__(self, message: str = "User quota exceeded", user_id: str | None = None):
        details = {"user_id": user_id} if user_id else None
        super().__init__(
            message=message,
            error_code="quota_exceeded",
            details=details,
        )
        self.user_id = user_id


class ServiceTimeoutError(AppException):
    """Raised when a service call times out.
    
    HTTP Status: 504 Gateway Timeout
    """
    
    def __init__(
        self, 
        message: str = "Service timeout",
        service_name: str | None = None,
        timeout_seconds: float | None = None,
    ):
        details = {}
        if service_name:
            details["service"] = service_name
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        super().__init__(
            message=message,
            error_code="timeout",
            details=details if details else None,
        )
        self.service_name = service_name
        self.timeout_seconds = timeout_seconds


class ServiceUnavailableError(AppException):
    """Raised when a required service is unavailable.
    
    HTTP Status: 503 Service Unavailable
    """
    
    def __init__(
        self, 
        message: str = "Service unavailable",
        service_name: str | None = None,
    ):
        details = {"service": service_name} if service_name else None
        super().__init__(
            message=message,
            error_code="service_unavailable",
            details=details,
        )
        self.service_name = service_name


class ContextBuildError(AppException):
    """Raised when context building fails.
    
    This error triggers fallback to template response.
    HTTP Status: 500 Internal Server Error (or fallback response)
    
    Requirements: 4.4
    """
    
    def __init__(
        self, 
        message: str = "Failed to build context",
        conversation_id: str | None = None,
    ):
        details = {"conversation_id": conversation_id} if conversation_id else None
        super().__init__(
            message=message,
            error_code="context_build_error",
            details=details,
        )
        self.conversation_id = conversation_id


class OrchestrationError(AppException):
    """Raised when orchestration fails.
    
    General error for orchestration failures that don't fit other categories.
    HTTP Status: 500 Internal Server Error
    
    Requirements: 4.5
    """
    
    def __init__(
        self, 
        message: str = "An error occurred during generation",
        step_name: str | None = None,
        original_error: Exception | None = None,
    ):
        details = {}
        if step_name:
            details["step"] = step_name
        super().__init__(
            message=message,
            error_code="orchestration_error",
            details=details if details else None,
        )
        self.step_name = step_name
        self.original_error = original_error


class RetryExhaustedError(AppException):
    """Raised when all retry attempts are exhausted.
    
    This typically triggers a fallback response.
    
    Requirements: 2.4, 4.2
    """
    
    def __init__(
        self, 
        message: str = "Retry attempts exhausted",
        max_retries: int | None = None,
        last_error: str | None = None,
    ):
        details = {}
        if max_retries is not None:
            details["max_retries"] = max_retries
        if last_error:
            details["last_error"] = last_error
        super().__init__(
            message=message,
            error_code="retry_exhausted",
            details=details if details else None,
        )
        self.max_retries = max_retries
        self.last_error = last_error


class CostLimitExceededError(AppException):
    """Raised when cost limit is exceeded during generation.
    
    This triggers forced use of cheap quality tier.
    
    Requirements: 4.3
    """
    
    def __init__(
        self, 
        message: str = "Cost limit exceeded",
        current_cost: float | None = None,
        limit: float | None = None,
    ):
        details = {}
        if current_cost is not None:
            details["current_cost_usd"] = current_cost
        if limit is not None:
            details["limit_usd"] = limit
        super().__init__(
            message=message,
            error_code="cost_limit_exceeded",
            details=details if details else None,
        )
        self.current_cost = current_cost
        self.limit = limit


def log_exception(exc: Exception, context: str | None = None) -> None:
    """Log an exception with context information.
    
    Args:
        exc: The exception to log.
        context: Optional context string for the log message.
    """
    if isinstance(exc, AppException):
        logger.error(
            f"{context or 'Error'}: [{exc.error_code}] {exc.message}",
            extra={"error_code": exc.error_code, "details": exc.details},
        )
    else:
        logger.exception(f"{context or 'Unexpected error'}: {exc}")
