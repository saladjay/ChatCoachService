"""
API v1 Router for ChatCoach.

This module aggregates all v1 endpoints under the /api/v1/ChatCoach prefix.
It includes health, predict, and metrics endpoints.

Requirements: 1.1, 1.2, 1.3
"""

from fastapi import APIRouter

from app.api.v1 import health, predict, chat_analysis


# Create main v1 router with ChatCoach prefix
# Requirement 1.1: Use prefix "/api/v1/ChatCoach" for all endpoints
api_router = APIRouter(prefix="/api/v1/ChatAnalysis")

# Requirement 1.2: Organize endpoints into logical groups
# Include health endpoint router
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"],
)

# Include predict endpoint router
api_router.include_router(
    predict.router,
    prefix="/predict",
    tags=["predict"],
)

# Include metrics endpoint router (chat_analysis)
api_router.include_router(
    chat_analysis.router,
    tags=["metrics"],
)
