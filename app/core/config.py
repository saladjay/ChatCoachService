"""
Application configuration using Pydantic Settings.
Supports loading from environment variables and .env files.
"""

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


# Global configuration instance
settings = AppConfig()
