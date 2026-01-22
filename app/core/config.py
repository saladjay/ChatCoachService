"""
Application configuration using Pydantic Settings.
Supports loading from environment variables and .env files.
"""

import os
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """LLM-related configuration."""
    
    model_config = SettingsConfigDict(env_prefix="LLM_")
    
    default_provider: str = "openai"
    default_model: str = "gpt-4"
    fallback_model: str = "gpt-3.5-turbo"
    cheap_model: str = "gpt-3.5-turbo"
    premium_model: str = "gpt-4-turbo"


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


class PromptConfig(BaseSettings):
    """Configuration for prompt optimization (Phase 3: Output Optimization)."""
    
    model_config = SettingsConfigDict(env_prefix="PROMPT_")
    
    include_reasoning: bool = False
    max_reply_tokens: int = 100
    use_compact_schemas: bool = True
    
    @classmethod
    def from_env(cls) -> "PromptConfig":
        """Load configuration from environment variables with validation."""
        include_reasoning = False
        max_reply_tokens = 100
        use_compact_schemas = True
        
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
        
        return cls(
            include_reasoning=include_reasoning,
            max_reply_tokens=max_reply_tokens,
            use_compact_schemas=use_compact_schemas
        )


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


# Global configuration instance
settings = AppConfig()
