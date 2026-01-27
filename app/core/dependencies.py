"""FastAPI dependency injection configuration.

This module provides FastAPI Depends functions for injecting services
into route handlers.

Requirements: 7.1
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import ServiceContainer, get_container
from app.db.session import get_async_session
from app.services.base import (
    BaseContextBuilder,
    BaseIntimacyChecker,
    BasePersonaInferencer,
    BaseReplyGenerator,
    BaseSceneAnalyzer,
)
from app.services.billing import BillingService
from app.services.orchestrator import Orchestrator
from app.services.persistence import PersistenceService
from app.services.user_profile_impl import BaseUserProfileService
from app.services.screenshot_parser import ScreenshotParserService
from app.services.session_categorized_cache_service import SessionCategorizedCacheService


def get_service_container() -> ServiceContainer:
    """Get the service container dependency.
    
    Returns:
        The global ServiceContainer instance.
    
    Requirements: 7.1
    """
    return get_container()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency.
    
    Yields:
        An async SQLAlchemy session.
    
    Requirements: 6.1
    """
    async for session in get_async_session():
        yield session


def get_persistence_service(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> PersistenceService:
    """Get the persistence service dependency.
    
    Args:
        session: The database session (injected).
    
    Returns:
        PersistenceService instance.
    
    Requirements: 6.1
    """
    return PersistenceService(session)


def get_orchestrator(
    container: Annotated[ServiceContainer, Depends(get_service_container)],
    persistence_service: Annotated[PersistenceService, Depends(get_persistence_service)],
) -> Orchestrator:
    """Get the orchestrator service dependency.
    
    Args:
        container: The service container (injected).
    
    Returns:
        Configured Orchestrator instance.
    
    Requirements: 7.1
    """
    return container.create_orchestrator(persistence_service=persistence_service)


def get_billing_service(
    container: Annotated[ServiceContainer, Depends(get_service_container)]
) -> BillingService:
    """Get the billing service dependency.
    
    Args:
        container: The service container (injected).
    
    Returns:
        BillingService instance.
    
    Requirements: 7.1
    """
    return container.get_billing_service()


def get_context_builder(
    container: Annotated[ServiceContainer, Depends(get_service_container)]
) -> BaseContextBuilder:
    """Get the context builder service dependency.
    
    Args:
        container: The service container (injected).
    
    Returns:
        Context builder instance.
    
    Requirements: 7.1
    """
    return container.get_context_builder()


def get_scene_analyzer(
    container: Annotated[ServiceContainer, Depends(get_service_container)]
) -> BaseSceneAnalyzer:
    """Get the scene analyzer service dependency.
    
    Args:
        container: The service container (injected).
    
    Returns:
        Scene analyzer instance.
    
    Requirements: 7.1
    """
    return container.get_scene_analyzer()


def get_persona_inferencer(
    container: Annotated[ServiceContainer, Depends(get_service_container)]
) -> BasePersonaInferencer:
    """Get the persona inferencer service dependency.
    
    Args:
        container: The service container (injected).
    
    Returns:
        Persona inferencer instance.
    
    Requirements: 7.1
    """
    return container.get_persona_inferencer()


def get_user_profile_service(
    container: Annotated[ServiceContainer, Depends(get_service_container)]
) -> BaseUserProfileService:
    return container.get_user_profile_service()


def get_reply_generator(
    container: Annotated[ServiceContainer, Depends(get_service_container)]
) -> BaseReplyGenerator:
    """Get the reply generator service dependency.
    
    Args:
        container: The service container (injected).
    
    Returns:
        Reply generator instance.
    
    Requirements: 7.1
    """
    return container.get_reply_generator()


def get_intimacy_checker(
    container: Annotated[ServiceContainer, Depends(get_service_container)]
) -> BaseIntimacyChecker:
    """Get the intimacy checker service dependency.
    
    Args:
        container: The service container (injected).
    
    Returns:
        Intimacy checker instance.
    
    Requirements: 7.1
    """
    return container.get_intimacy_checker()


def get_screenshot_parser(
    container: Annotated[ServiceContainer, Depends(get_service_container)]
) -> ScreenshotParserService:
    """Get the screenshot parser service dependency.
    
    Args:
        container: The service container (injected).
    
    Returns:
        ScreenshotParserService instance.
    """
    return container.get_screenshot_parser()


def get_session_categorized_cache_service(
    container: Annotated[ServiceContainer, Depends(get_service_container)]
) -> SessionCategorizedCacheService:
    return container.get_session_categorized_cache_service()


# Type aliases for cleaner route signatures
ServiceContainerDep = Annotated[ServiceContainer, Depends(get_service_container)]
OrchestratorDep = Annotated[Orchestrator, Depends(get_orchestrator)]
BillingServiceDep = Annotated[BillingService, Depends(get_billing_service)]
ContextBuilderDep = Annotated[BaseContextBuilder, Depends(get_context_builder)]
SceneAnalyzerDep = Annotated[BaseSceneAnalyzer, Depends(get_scene_analyzer)]
PersonaInferencerDep = Annotated[BasePersonaInferencer, Depends(get_persona_inferencer)]
UserProfileServiceDep = Annotated[BaseUserProfileService, Depends(get_user_profile_service)]
ReplyGeneratorDep = Annotated[BaseReplyGenerator, Depends(get_reply_generator)]
IntimacyCheckerDep = Annotated[BaseIntimacyChecker, Depends(get_intimacy_checker)]
ScreenshotParserDep = Annotated[ScreenshotParserService, Depends(get_screenshot_parser)]
SessionCategorizedCacheServiceDep = Annotated[
    SessionCategorizedCacheService, Depends(get_session_categorized_cache_service)
]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
PersistenceServiceDep = Annotated[PersistenceService, Depends(get_persistence_service)]
