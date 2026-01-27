"""Service container for dependency injection.

This module implements a service container that:
- Manages all service instances
- Supports registration and retrieval of services
- Allows configuration-based switching between Mock and real implementations

Requirements: 7.1, 7.2, 7.3
"""

from typing import Any, TypeVar, Generic, Type
from enum import Enum

from app.core.config import AppConfig, settings
from app.services.base import (
    BaseContextBuilder,
    BaseIntimacyChecker,
    BasePersonaInferencer,
    BaseReplyGenerator,
    BaseSceneAnalyzer,
)
from app.services.mocks import (
    MockContextBuilder,
    MockIntimacyChecker,
    MockPersonaInferencer,
    MockReplyGenerator,
    MockSceneAnalyzer,
)
from app.services.context_impl import ContextBuilder
from app.services.billing import BillingService
from app.services.orchestrator import Orchestrator
from app.models.schemas import OrchestratorConfig
from app.services.llm_adapter import (
    BaseLLMAdapter,
    LLMAdapterImpl,
    create_llm_adapter,
)
from app.services.logging_llm_adapter import LoggingLLMAdapter
from app.services.reply_generator_impl import LLMAdapterReplyGenerator
from app.services.scene_analyzer_impl import SceneAnalyzer
from app.services.user_profile_impl import (
    BaseUserProfileService,
    UserProfileService,
    UserProfilePersonaInferencer,
)
from app.services.persistence import PersistenceService
from app.services.intimacy_checker_impl import ModerationServiceIntimacyChecker
from app.services.screenshot_parser import ScreenshotParserService
from app.services.image_fetcher import ImageFetcher
from app.services.prompt_builder import PromptBuilder
from app.services.multimodal_llm_adapter import MultimodalLLMClient
from app.services.result_normalizer import ResultNormalizer


T = TypeVar("T")


class ServiceMode(str, Enum):
    """Service implementation mode."""
    MOCK = "mock"
    REAL = "real"


class ServiceContainer:
    """Dependency injection container for managing service instances.
    
    Provides centralized management of all service instances with support
    for switching between mock and real implementations via configuration.
    
    Attributes:
        config: Application configuration.
        _services: Dictionary storing registered service instances.
        _mode: Current service mode (mock or real).
    
    Requirements: 7.1, 7.2, 7.3
    """

    def __init__(self, config: AppConfig | None = None, mode: ServiceMode = ServiceMode.MOCK):
        """Initialize the service container.
        
        Args:
            config: Application configuration. Uses global settings if not provided.
            mode: Service mode determining whether to use mock or real implementations.
        """
        self.config = config or settings
        self._services: dict[str, Any] = {}
        self._mode = mode
        self._initialized = False

    @property
    def mode(self) -> ServiceMode:
        """Get the current service mode."""
        return self._mode

    def set_mode(self, mode: ServiceMode) -> None:
        """Set the service mode and reinitialize services.
        
        Args:
            mode: The new service mode.
        
        Requirements: 7.2
        """
        if self._mode != mode:
            self._mode = mode
            self._services.clear()
            self._initialized = False

    def register(self, name: str, service: Any) -> None:
        """Register a service instance.
        
        Args:
            name: Unique name for the service.
            service: The service instance to register.
        
        Requirements: 7.1
        """
        self._services[name] = service

    def get(self, name: str) -> Any:
        """Get a registered service by name.
        
        Args:
            name: The service name.
        
        Returns:
            The registered service instance.
        
        Raises:
            KeyError: If service is not registered.
        
        Requirements: 7.1
        """
        if name not in self._services:
            raise KeyError(f"Service '{name}' not registered")
        return self._services[name]

    def has(self, name: str) -> bool:
        """Check if a service is registered.
        
        Args:
            name: The service name.
        
        Returns:
            True if service is registered, False otherwise.
        """
        return name in self._services

    def _initialize_services(self) -> None:
        """Initialize all services based on current mode.
        
        Creates and registers all required services using either
        mock or real implementations based on the current mode.
        
        Requirements: 7.2, 7.3, 7.4
        """
        if self._initialized:
            return

        # Register LLM Adapter (used by reply generator)
        if not self.has("llm_adapter"):
            self.register("llm_adapter", self._create_llm_adapter())

        # Register UserProfile Service (used by persona inferencer)
        if not self.has("user_profile_service"):
            self.register("user_profile_service", self._create_user_profile_service())

        # Register context builder
        if not self.has("context_builder"):
            self.register("context_builder", self._create_context_builder())

        # Register scene analyzer
        if not self.has("scene_analyzer"):
            self.register("scene_analyzer", self._create_scene_analyzer())

        # Phase 2: Register strategy planner (optional, for token optimization)
        if not self.has("strategy_planner"):
            self.register("strategy_planner", self._create_strategy_planner())

        # Register persona inferencer (uses UserProfile Service in REAL mode)
        if not self.has("persona_inferencer"):
            self.register("persona_inferencer", self._create_persona_inferencer())

        # Register reply generator (uses LLM Adapter in REAL mode)
        if not self.has("reply_generator"):
            self.register("reply_generator", self._create_reply_generator())

        # Register intimacy checker
        if not self.has("intimacy_checker"):
            self.register("intimacy_checker", self._create_intimacy_checker())

        # Register billing service
        if not self.has("billing_service"):
            self.register(
                "billing_service",
                BillingService(default_quota_usd=self.config.billing.default_user_quota_usd)
            )

        # Register screenshot parser service components
        if not self.has("image_fetcher"):
            self.register("image_fetcher", self._create_image_fetcher())
        
        if not self.has("prompt_builder"):
            self.register("prompt_builder", self._create_prompt_builder())
        
        if not self.has("multimodal_llm_client"):
            self.register("multimodal_llm_client", self._create_multimodal_llm_client())
        
        if not self.has("result_normalizer"):
            self.register("result_normalizer", self._create_result_normalizer())
        
        if not self.has("screenshot_parser"):
            self.register("screenshot_parser", self._create_screenshot_parser())

        self._initialized = True

    def _create_llm_adapter(self) -> BaseLLMAdapter:
        """Create LLM Adapter using over-seas-llm-platform-service.
        
        Returns:
            LLM Adapter instance.
        
        Requirements: 3.3
        """
        # Use the real LLM Adapter implementation from over-seas-llm-platform-service
        adapter = create_llm_adapter()
        if self.config.trace.enabled:
            return LoggingLLMAdapter(adapter)
        return adapter

    def _create_user_profile_service(self) -> BaseUserProfileService:
        """Create UserProfile Service.
        
        Returns:
            UserProfile Service instance.
        
        Requirements: 3.2
        """
        # UserProfile Service needs LLM Adapter for scenario analysis
        llm_adapter = self.get("llm_adapter") if self.has("llm_adapter") else self._create_llm_adapter()
        return UserProfileService(llm_adapter=llm_adapter)

    def _create_context_builder(self) -> BaseContextBuilder:
        """Create context builder based on mode.
        
        Returns:
            Context builder instance (mock or real).
        
        Requirements: 7.2, 7.4
        """
        if self._mode == ServiceMode.MOCK:
            return MockContextBuilder()
        # Real implementation uses LLM Adapter for context analysis
        llm_adapter = self.get("llm_adapter") if self.has("llm_adapter") else self._create_llm_adapter()
        return ContextBuilder(llm_adapter=llm_adapter)

    def _create_scene_analyzer(self) -> BaseSceneAnalyzer:
        """Create scene analyzer based on mode.
        
        Returns:
            Scene analyzer instance (mock or real).
        
        Requirements: 7.2, 7.4
        """
        if self._mode == ServiceMode.MOCK:
            return MockSceneAnalyzer()
        llm_adapter = self.get("llm_adapter") if self.has("llm_adapter") else self._create_llm_adapter()
        return SceneAnalyzer(llm_adapter=llm_adapter)
    
    def _create_strategy_planner(self):
        """Create strategy planner for Phase 2 optimization.
        
        Returns:
            StrategyPlanner instance or None if in MOCK mode.
        """
        if self._mode == ServiceMode.MOCK:
            return None  # No strategy planner in mock mode
        
        from app.services.strategy_planner import StrategyPlanner
        llm_adapter = self.get("llm_adapter") if self.has("llm_adapter") else self._create_llm_adapter()
        return StrategyPlanner(llm_adapter=llm_adapter)

    def _create_persona_inferencer(self) -> BasePersonaInferencer:
        """Create persona inferencer based on mode.
        
        Returns:
            Persona inferencer instance (mock or real).
        
        Requirements: 3.2, 7.2, 7.4
        """
        if self._mode == ServiceMode.MOCK:
            return MockPersonaInferencer()
        # Real implementation uses UserProfile Service
        user_profile_service = self.get("user_profile_service")
        return UserProfilePersonaInferencer(user_profile_service)

    def _create_reply_generator(self) -> BaseReplyGenerator:
        """Create reply generator based on mode.
        
        Returns:
            Reply generator instance (mock or real).
        
        Requirements: 3.3, 7.2, 7.4
        """
        if self._mode == ServiceMode.MOCK:
            return MockReplyGenerator()
        # Real implementation uses LLM Adapter
        llm_adapter = self.get("llm_adapter")
        user_profile_service = self.get("user_profile_service")
        strategy_planner = self.get("strategy_planner") if self.has("strategy_planner") else None
        
        # Phase 3: Pass PromptConfig to reply generator
        return LLMAdapterReplyGenerator(
            llm_adapter, 
            user_profile_service,
            strategy_planner=strategy_planner,
            prompt_config=self.config.prompt,  # Phase 3
        )

    def _create_intimacy_checker(self) -> BaseIntimacyChecker:
        """Create intimacy checker based on mode.
        
        Returns:
            Intimacy checker instance (mock or real).
        
        Requirements: 7.2, 7.4
        """
        if self._mode == ServiceMode.MOCK:
            return MockIntimacyChecker()
        cfg = self.config.moderation
        llm_cfg = self.config.llm
        llm_adapter = self.get("llm_adapter") if self.has("llm_adapter") else self._create_llm_adapter()
        return ModerationServiceIntimacyChecker(
            base_url=cfg.base_url,
            timeout_seconds=cfg.timeout_seconds,
            policy=cfg.policy,
            fail_open=cfg.fail_open,
            use_library=cfg.use_library,
            allow_http_fallback=cfg.allow_http_fallback,
            llm_adapter=llm_adapter,
            llm_provider=llm_cfg.default_provider,
            llm_model=llm_cfg.default_model,
        )

    def get_context_builder(self) -> BaseContextBuilder:
        """Get the context builder service.
        
        Returns:
            Context builder instance.
        """
        self._initialize_services()
        return self.get("context_builder")

    def get_scene_analyzer(self) -> BaseSceneAnalyzer:
        """Get the scene analyzer service.
        
        Returns:
            Scene analyzer instance.
        """
        self._initialize_services()
        return self.get("scene_analyzer")

    def get_persona_inferencer(self) -> BasePersonaInferencer:
        """Get the persona inferencer service.
        
        Returns:
            Persona inferencer instance.
        """
        self._initialize_services()
        return self.get("persona_inferencer")

    def get_reply_generator(self) -> BaseReplyGenerator:
        """Get the reply generator service.
        
        Returns:
            Reply generator instance.
        """
        self._initialize_services()
        return self.get("reply_generator")

    def get_intimacy_checker(self) -> BaseIntimacyChecker:
        """Get the intimacy checker service.
        
        Returns:
            Intimacy checker instance.
        """
        self._initialize_services()
        return self.get("intimacy_checker")

    def get_billing_service(self) -> BillingService:
        """Get the billing service.
        
        Returns:
            Billing service instance.
        """
        self._initialize_services()
        return self.get("billing_service")

    def get_llm_adapter(self) -> BaseLLMAdapter:
        """Get the LLM Adapter service.
        
        Returns:
            LLM Adapter instance.
        
        Requirements: 3.3
        """
        self._initialize_services()
        return self.get("llm_adapter")

    def get_user_profile_service(self) -> BaseUserProfileService:
        """Get the UserProfile Service.
        
        Returns:
            UserProfile Service instance.
        
        Requirements: 3.2
        """
        self._initialize_services()
        return self.get("user_profile_service")
    
    def get_strategy_planner(self):
        """Get the StrategyPlanner service.
        
        Returns:
            StrategyPlanner instance or None if not available.
        """
        self._initialize_services()
        return self.get("strategy_planner") if self.has("strategy_planner") else None

    def _create_image_fetcher(self) -> ImageFetcher:
        """Create ImageFetcher for screenshot parsing.
        
        Returns:
            ImageFetcher instance.
        """
        return ImageFetcher(timeout=30.0)

    def _create_prompt_builder(self) -> PromptBuilder:
        """Create PromptBuilder for screenshot parsing.
        
        Returns:
            PromptBuilder instance.
        """
        return PromptBuilder()

    def _create_multimodal_llm_client(self) -> MultimodalLLMClient:
        """Create MultimodalLLMClient for screenshot parsing.
        
        Returns:
            MultimodalLLMClient instance.
        """
        return MultimodalLLMClient(config=self.config)

    def _create_result_normalizer(self) -> ResultNormalizer:
        """Create ResultNormalizer for screenshot parsing.
        
        Returns:
            ResultNormalizer instance.
        """
        return ResultNormalizer()

    def _create_screenshot_parser(self) -> ScreenshotParserService:
        """Create ScreenshotParserService with all dependencies.
        
        Returns:
            ScreenshotParserService instance.
        """
        return ScreenshotParserService(
            image_fetcher=self.get("image_fetcher"),
            prompt_builder=self.get("prompt_builder"),
            llm_client=self.get("multimodal_llm_client"),
            result_normalizer=self.get("result_normalizer"),
        )

    def get_screenshot_parser(self) -> ScreenshotParserService:
        """Get the screenshot parser service.
        
        Returns:
            ScreenshotParserService instance.
        """
        self._initialize_services()
        return self.get("screenshot_parser")

    def create_orchestrator(
        self,
        persistence_service: PersistenceService | None = None,
    ) -> Orchestrator:
        """Create an orchestrator with all required dependencies.
        
        Returns:
            Configured Orchestrator instance.
        
        Requirements: 7.1
        """
        self._initialize_services()
        
        orchestrator_config = OrchestratorConfig(
            max_retries=self.config.orchestrator.max_retries,
            timeout_seconds=self.config.orchestrator.timeout_seconds,
            cost_limit_usd=self.config.billing.cost_limit_usd,
            fallback_model=self.config.llm.fallback_model,
        )
        
        strategy_planner = self.get_strategy_planner()
        
        return Orchestrator(
            context_builder=self.get_context_builder(),
            scene_analyzer=self.get_scene_analyzer(),
            persona_inferencer=self.get_persona_inferencer(),
            reply_generator=self.get_reply_generator(),
            intimacy_checker=self.get_intimacy_checker(),
            billing_service=self.get_billing_service(),
            persistence_service=persistence_service,
            config=orchestrator_config,
            billing_config=self.config.billing,
            strategy_planner=strategy_planner,
        )


# Global container instance
_container: ServiceContainer | None = None


def get_container() -> ServiceContainer:
    """Get the global service container instance.
    
    Creates a new container if one doesn't exist.
    Uses REAL mode by default for production use.
    
    Returns:
        The global ServiceContainer instance.
    """
    global _container
    if _container is None:
        _container = ServiceContainer(mode=ServiceMode.REAL)
    return _container


def reset_container() -> None:
    """Reset the global container instance.
    
    Useful for testing to ensure a fresh container state.
    """
    global _container
    _container = None
