"""
FastAPI application entry point.
Configures CORS, exception handlers, and routes.

Requirements: 1.1, 4.5
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    ContextBuildError,
    CostLimitExceededError,
    OrchestrationError,
    QuotaExceededError,
    RetryExhaustedError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    ValidationError,
    log_exception,
)
from app.db.session import close_db, init_db


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    from app.core.v1_config import get_v1_config
    from app.core.container import get_container
    get_v1_config().setup_logging()
    
    # Print LLM configuration on startup
    print_llm_configuration()
    
    # Startup: Initialize database
    await init_db()

    container = get_container()
    categorized_cache_service = container.get_session_categorized_cache_service()
    try:
        await categorized_cache_service.start()
    except Exception as e:
        logger.warning(
            f"SessionCategorizedCacheService start failed (continuing without Redis cache): {e}",
            exc_info=True,
        )
        try:
            await categorized_cache_service.stop()
        except Exception:
            logger.warning("SessionCategorizedCacheService cleanup failed", exc_info=True)
    yield

    try:
        await categorized_cache_service.stop()
    except Exception as e:
        logger.warning(f"SessionCategorizedCacheService stop failed: {e}", exc_info=True)
    # Shutdown: Close database connections
    await close_db()


def print_llm_configuration() -> None:
    """Print LLM configuration on startup for debugging."""
    try:
        import sys
        import os
        from pathlib import Path
        
        print("\n" + "=" * 80)
        print("LLM CONFIGURATION")
        print("=" * 80)
        
        # Print app-level settings
        print(f"\nApplication Settings (from .env):")
        print(f"  Default Provider:           {settings.llm.default_provider}")
        print(f"  Default Model:              {settings.llm.default_model or 'N/A'}")
        print(f"  Multimodal Image Format:    {settings.llm.multimodal_image_format}")
        
        # Get disable_quality_routing from environment variable
        disable_routing = os.environ.get("LLM_DISABLE_QUALITY_ROUTING", "").lower() in ("true", "1", "yes")
        print(f"  Disable Quality Routing:    {disable_routing}")
        
        # Load LLM adapter config
        llm_adapter_path = Path(__file__).parent.parent / "core" / "llm_adapter"
        if str(llm_adapter_path) not in sys.path:
            sys.path.insert(0, str(llm_adapter_path))
        
        from llm_adapter import ConfigManager
        
        config_path = llm_adapter_path / "config.yaml"
        config_manager = ConfigManager(str(config_path))
        default_provider = config_manager.get_default_provider()
        
        print(f"\nLLM Adapter Configuration (from config.yaml):")
        print(f"  Default Provider:           {default_provider}")
        
        # Get provider config
        try:
            provider_config = config_manager.get_provider_config(default_provider)
            
            print(f"\nProvider '{default_provider}' Configuration:")
            print(f"  API Key:                    {'*' * 20}...{provider_config.api_key[-4:] if provider_config.api_key else 'NOT SET'}")
            
            if hasattr(provider_config, 'base_url') and provider_config.base_url:
                print(f"  Base URL:                   {provider_config.base_url}")
            
            print(f"  Models:")
            if hasattr(provider_config.models, 'cheap'):
                print(f"    cheap:                    {provider_config.models.cheap}")
            if hasattr(provider_config.models, 'normal'):
                print(f"    normal:                   {provider_config.models.normal}")
            if hasattr(provider_config.models, 'premium'):
                print(f"    premium:                  {provider_config.models.premium}")
            if hasattr(provider_config.models, 'multimodal'):
                print(f"    multimodal:               {provider_config.models.multimodal}")
            
            # Print generation params if available
            if hasattr(provider_config, 'generation_params') and provider_config.generation_params:
                print(f"  Generation Parameters:")
                # Convert to dict if it's a Pydantic model
                if hasattr(provider_config.generation_params, 'model_dump'):
                    params_dict = provider_config.generation_params.model_dump()
                elif hasattr(provider_config.generation_params, 'dict'):
                    params_dict = provider_config.generation_params.dict()
                elif isinstance(provider_config.generation_params, dict):
                    params_dict = provider_config.generation_params
                else:
                    params_dict = vars(provider_config.generation_params)
                
                for key, value in params_dict.items():
                    if value is not None:  # Only show non-None values
                        print(f"    {key:24s}  {value}")
        
        except Exception as e:
            print(f"  Error loading provider config: {e}")
        
        # Print proxy configuration
        proxy_url = config_manager.get_proxy_url()
        print(f"\nProxy Configuration:")
        if proxy_url:
            print(f"  Proxy URL:                  {proxy_url}")
            print(f"  Status:                     ENABLED")
        else:
            print(f"  Status:                     DISABLED")
        
        # Print quality routing configuration
        print(f"\nQuality Routing:")
        if disable_routing:
            print(f"  Status:                     DISABLED (using default provider only)")
        else:
            print(f"  Status:                     ENABLED (with fallback)")
            
            # Show available providers for each quality level
            from llm_adapter.router import Router
            router = Router(config_manager)
            
            for quality in ["low", "medium", "high"]:
                available = router.get_available_providers(quality)
                if available:
                    providers_str = ", ".join([f"{p}({m})" for p, m in available[:3]])
                    print(f"    {quality:8s}:              {providers_str}")
        
        print("=" * 80 + "\n")
        
    except Exception as e:
        logger.error(f"Failed to print LLM configuration: {e}", exc_info=True)
        print(f"\n⚠ Warning: Could not load LLM configuration: {e}\n")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Requirements: 1.4, 1.5, 10.3, 10.4
    """
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        # Requirement 1.4, 1.5: Configure OpenAPI docs URLs
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    allow_credentials = settings.cors_allow_credentials
    if "*" in settings.cors_origins and allow_credentials:
        allow_credentials = False
        logger.warning(
            "CORS allow_credentials=True is not compatible with allow_origins=['*']; "
            "forcing allow_credentials=False. Configure explicit origins to use credentials."
        )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    
    # Add request logging middleware for v1 endpoints
    # Requirements: 10.3, 10.4
    from app.core.v1_config import get_v1_config
    from app.api.v1.middleware import RequestLoggingMiddleware
    
    v1_config = get_v1_config()
    if v1_config.logging.enable_request_logging:
        app.add_middleware(RequestLoggingMiddleware)
        logger.info("Request logging middleware enabled")
    
    # Register exception handlers
    register_exception_handlers(app)
    
    # Register routes
    register_routes(app)
    
    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers.
    
    Maps custom exceptions to appropriate HTTP status codes and response formats.
    Ensures internal details are not exposed to clients.
    
    Requirements: 4.5
    """
    
    @app.exception_handler(ValidationError)
    async def validation_error_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        """Handle validation errors with 400 status."""
        log_exception(exc, "Validation error")
        return JSONResponse(
            status_code=400,
            content=exc.to_dict(),
        )
    
    @app.exception_handler(QuotaExceededError)
    async def quota_exceeded_handler(
        request: Request, exc: QuotaExceededError
    ) -> JSONResponse:
        """Handle quota exceeded errors with 402 status."""
        log_exception(exc, "Quota exceeded")
        return JSONResponse(
            status_code=402,
            content={
                "error": exc.error_code,
                "message": exc.message,
            },
        )
    
    @app.exception_handler(ServiceTimeoutError)
    async def timeout_handler(
        request: Request, exc: ServiceTimeoutError
    ) -> JSONResponse:
        """Handle service timeout errors with 504 status."""
        log_exception(exc, "Service timeout")
        return JSONResponse(
            status_code=504,
            content={
                "error": exc.error_code,
                "message": exc.message,
            },
        )
    
    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_handler(
        request: Request, exc: ServiceUnavailableError
    ) -> JSONResponse:
        """Handle service unavailable errors with 503 status."""
        log_exception(exc, "Service unavailable")
        return JSONResponse(
            status_code=503,
            content={
                "error": exc.error_code,
                "message": exc.message,
            },
        )
    
    @app.exception_handler(ContextBuildError)
    async def context_build_error_handler(
        request: Request, exc: ContextBuildError
    ) -> JSONResponse:
        """Handle context build errors with 500 status.
        
        Note: In practice, the orchestrator catches this and returns
        a fallback response. This handler is for cases where the error
        propagates to the API layer.
        """
        log_exception(exc, "Context build error")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "Failed to process request context",
            },
        )
    
    @app.exception_handler(OrchestrationError)
    async def orchestration_error_handler(
        request: Request, exc: OrchestrationError
    ) -> JSONResponse:
        """Handle orchestration errors with 500 status.
        
        Returns a user-friendly message without exposing internal details.
        Requirements: 4.5
        """
        log_exception(exc, "Orchestration error")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "An error occurred during generation",
            },
        )
    
    @app.exception_handler(RetryExhaustedError)
    async def retry_exhausted_handler(
        request: Request, exc: RetryExhaustedError
    ) -> JSONResponse:
        """Handle retry exhausted errors with 500 status.
        
        Note: In practice, the orchestrator handles this by returning
        a fallback response. This handler is for edge cases.
        """
        log_exception(exc, "Retry exhausted")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "Unable to generate a suitable response",
            },
        )
    
    @app.exception_handler(CostLimitExceededError)
    async def cost_limit_handler(
        request: Request, exc: CostLimitExceededError
    ) -> JSONResponse:
        """Handle cost limit exceeded errors.
        
        Note: This is typically handled internally by forcing cheap quality.
        This handler is for cases where the error needs to be surfaced.
        """
        log_exception(exc, "Cost limit exceeded")
        return JSONResponse(
            status_code=402,
            content={
                "error": exc.error_code,
                "message": "Cost limit exceeded for this request",
            },
        )
    
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        """Handle generic application exceptions with 500 status."""
        log_exception(exc, "Application error")
        return JSONResponse(
            status_code=500,
            content={
                "error": exc.error_code,
                "message": exc.message,
            },
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions with 500 status.
        
        Logs the full exception but returns a generic message to the client
        to avoid exposing internal details.
        
        Requirements: 4.5
        """
        logger.exception(f"Unexpected error: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred",
            },
        )


def register_routes(app: FastAPI) -> None:
    """Register API routes.
    
    Requirements: 1.4, 1.5
    """
    
    # Register API routes
    from app.api.generate import router as generate_router
    from app.api.fetch import router as fetch_router
    from app.api.context import router as context_router
    from app.api.user_profile import router as user_profile_router
    from app.api.screenshot import router as screenshot_router
    from app.api.health import router as health_router
    
    app.include_router(health_router)
    
    app.include_router(generate_router, prefix=settings.api_prefix)
    app.include_router(fetch_router, prefix=settings.api_prefix)
    app.include_router(context_router, prefix=settings.api_prefix)
    app.include_router(user_profile_router, prefix=settings.api_prefix)
    app.include_router(screenshot_router, prefix=settings.api_prefix)
    app.include_router(health_router, prefix=settings.api_prefix)
    
    # Register v1 API router
    # Requirement 1.1, 1.2, 1.3: Register v1 router with /api/v1/ChatCoach prefix
    from app.api.v1.router import api_router as v1_router
    app.include_router(v1_router)


# Create the application instance
app = create_app()
