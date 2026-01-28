# Service Layer

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
from app.services.billing import BillingService
from app.services.orchestrator import Orchestrator
from app.services.fallback import FallbackStrategy
from app.services.persistence import PersistenceService
from app.services.llm_adapter import (
    BaseLLMAdapter,
    LLMAdapterImpl,
    LLMCall,
    create_llm_adapter,
)
from app.services.reply_generator_impl import LLMAdapterReplyGenerator
from app.services.user_profile_impl import (
    BaseUserProfileService,
    UserProfileService,
    UserProfilePersonaInferencer,
)
from app.core.exceptions import (
    OrchestrationError,
    QuotaExceededError,
    ContextBuildError,
)

__all__ = [
    # Abstract base classes
    "BaseContextBuilder",
    "BaseSceneAnalyzer",
    "BasePersonaInferencer",
    "BaseReplyGenerator",
    "BaseIntimacyChecker",
    # Mock implementations
    "MockContextBuilder",
    "MockSceneAnalyzer",
    "MockPersonaInferencer",
    "MockReplyGenerator",
    "MockIntimacyChecker",
    # Core services
    "BillingService",
    "Orchestrator",
    "OrchestrationError",
    "QuotaExceededError",
    "ContextBuildError",
    "FallbackStrategy",
    "PersistenceService",
    # LLM Adapter (Requirements: 3.3)
    "BaseLLMAdapter",
    "LLMAdapterImpl",
    "LLMAdapterReplyGenerator",
    "LLMCall",
    "create_llm_adapter",
    # UserProfile Service (Requirements: 3.2)
    "BaseUserProfileService",
    "UserProfileService",
    "UserProfilePersonaInferencer",
]
