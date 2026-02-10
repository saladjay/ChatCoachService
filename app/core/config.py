"""
Application configuration using Pydantic Settings.
Supports loading from environment variables and .env files.
"""

import os
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """LLM-related configuration.
    
    Note: These are fallback values. The actual LLM configuration is loaded from
    core/llm_adapter/config.yaml by the LLMAdapter at runtime.
    
    To see the actual provider and models being used, check:
    - core/llm_adapter/config.yaml (main configuration)
    - Environment variables (OPENROUTER_API_KEY, etc.)
    """
    
    model_config = SettingsConfigDict(env_prefix="LLM_")
    
    # These are fallback values only - actual config is in core/llm_adapter/config.yaml
    default_provider: str = "openrouter"
    default_model: str = "google/gemini-2.0-flash-lite-001"
    fallback_model: str = "google/gemini-2.0-flash-lite-001"
    cheap_model: str = "google/gemini-2.0-flash-lite-001"
    premium_model: str = "google/gemini-2.0-flash-lite-001"
    
    # Multimodal image transport format: "base64" or "url"
    # base64: Compress and encode image as base64 (recommended for most providers)
    # url: Send image URL directly (faster but not all providers support it)
    multimodal_image_format: Literal["base64", "url"] = "base64"
    
    # Whether to compress images before sending to LLM
    # true: Compress to 800px max dimension (saves tokens, faster)
    # false: Use original image size (better quality, more tokens)
    multimodal_image_compress: bool = True


class OrchestratorConfig(BaseSettings):
    """Orchestrator configuration for retry and timeout settings."""
    
    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_")
    
    max_retries: int = 3
    timeout_seconds: float = 30.0
    retry_delay_seconds: float = 0.5
    exponential_backoff: bool = True


class BillingConfig(BaseSettings):
    """Billing and cost limit configuration."""
    
    model_config = SettingsConfigDict(env_prefix="BILLING_")
    
    cost_limit_usd: float = 0.1
    default_user_quota_usd: float = 10.0


class DatabaseConfig(BaseSettings):
    """Database connection configuration."""
    
    model_config = SettingsConfigDict(env_prefix="DB_")
    
    url: str = "sqlite+aiosqlite:///./conversation.db"
    echo: bool = False


class TraceConfig(BaseSettings):
    """Trace logging configuration (step inputs/outputs + LLM prompts)."""

    model_config = SettingsConfigDict(env_prefix="TRACE_")

    enabled: bool = False
    level: Literal["error", "info", "debug"] = "info"
    file_path: str = "logs/trace.jsonl"
    log_llm_prompt: bool = True
    log_timing: bool = False  # Enable timing logs for performance monitoring


class PromptConfig(BaseSettings):
    """Configuration for prompt optimization (Phase 3: Output Optimization)."""
    
    model_config = SettingsConfigDict(env_prefix="PROMPT_")
    
    include_reasoning: bool = False
    max_reply_tokens: int = 100
    use_compact_schemas: bool = True
    context_max_messages: int = 20
    
    @classmethod
    def from_env(cls) -> "PromptConfig":
        """Load configuration from environment variables with validation."""
        include_reasoning = False
        max_reply_tokens = 100
        use_compact_schemas = True
        context_max_messages = 20
        
        # Parse include_reasoning
        reasoning_str = os.getenv("PROMPT_INCLUDE_REASONING", "false").lower()
        if reasoning_str in ("true", "1", "yes"):
            include_reasoning = True
        
        # Parse max_reply_tokens with validation
        try:
            tokens = int(os.getenv("PROMPT_MAX_REPLY_TOKENS", "100"))
            if 20 <= tokens <= 500:
                max_reply_tokens = tokens
            else:
                # Clamp to valid range
                max_reply_tokens = max(20, min(500, tokens))
        except (ValueError, TypeError):
            pass  # Use default
        
        # Parse use_compact_schemas
        compact_str = os.getenv("PROMPT_USE_COMPACT_SCHEMAS", "true").lower()
        if compact_str in ("false", "0", "no"):
            use_compact_schemas = False

        # Parse context_max_messages with validation
        try:
            max_messages = int(os.getenv("PROMPT_CONTEXT_MAX_MESSAGES", "20"))
            if 1 <= max_messages <= 50:
                context_max_messages = max_messages
            else:
                context_max_messages = max(1, min(50, max_messages))
        except (ValueError, TypeError):
            pass
        
        return cls(
            include_reasoning=include_reasoning,
            max_reply_tokens=max_reply_tokens,
            use_compact_schemas=use_compact_schemas,
            context_max_messages=context_max_messages,
        )
class ModerationClientConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MODERATION_")

    base_url: str = "http://localhost:8000"
    timeout_seconds: float = 5.0
    policy: str = "default"
    fail_open: bool = True
    use_library: bool = True
    allow_http_fallback: bool = True


class CacheConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CACHE_")

    redis_url: str = "redis://localhost:6379/0"
    sqlite_path: str = "./session_cache.db"
    ttl_seconds: int = 7200
    timeline_max_items: int = 500
    cleanup_interval_seconds: int = 300
    redis_key_prefix: str = "cache"


class DebugConfig(BaseSettings):
    """Debug and logging control configuration."""
    
    model_config = SettingsConfigDict(env_prefix="DEBUG_")
    
    # Race strategy debug settings
    # When True, wait for all models to complete and log all results
    # When False, stop after first valid result (faster, production mode)
    race_wait_all: bool = False
    
    # Detailed logging for different components
    log_merge_step_extraction: bool = True  # Log extracted bubbles from merge_step
    log_screenshot_parse: bool = True  # Log extracted dialogs from screenshot_parse
    log_race_strategy: bool = True  # Log race strategy details
    log_llm_calls: bool = False  # Log detailed LLM call information
    log_validation: bool = False  # Log validation details
    log_premium_bbox_calculation: bool = False  # Log detailed bbox coordinate calculation for premium model


class AppConfig(BaseSettings):
    """Main application configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Application settings
    app_name: str = "Conversation Generation Service"
    app_version: str = "0.1.0"
    debug: bool = False
    no_reply_cache: bool = True
    no_strategy_planner: bool = True
    no_persona_cache: bool = True
    no_intimacy_check: bool = False  # Disable intimacy check if True
    log_failed_json_replies: bool = False  # Log failed JSON parsing replies to file
    
    # Merge Step Configuration
    use_merge_step: bool = False  # Enable merge_step optimized flow if True
    
    # API settings
    api_prefix: str = "/api/v1"
    
    # CORS settings
    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]
    
    # Model selection strategy
    model_selection_strategy: Literal["quality", "cost", "balanced"] = "balanced"
    
    # Sub-configurations
    llm: LLMConfig = LLMConfig()
    orchestrator: OrchestratorConfig = OrchestratorConfig()
    billing: BillingConfig = BillingConfig()
    database: DatabaseConfig = DatabaseConfig()
    trace: TraceConfig = TraceConfig()
    prompt: PromptConfig = PromptConfig.from_env()
    debug_config: DebugConfig = DebugConfig()
    moderation: ModerationClientConfig = ModerationClientConfig()
    cache: CacheConfig = CacheConfig()


# Global configuration instance
settings = AppConfig()
