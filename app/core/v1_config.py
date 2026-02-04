"""
Configuration models for ChatCoach API v1.
Includes screenshot processing configuration and logging setup.
"""

import logging
import os
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class ScreenshotConfig(BaseSettings):
    """Configuration for screenshot processing."""
    
    model_config = SettingsConfigDict(
        env_prefix="V1_SCREENSHOT__",
        extra="ignore",
    )
    
    supported_languages: list[str] = Field(
        default=["en", "zh", "es", "fr", "de", "ja", "ko"],
        description="List of supported languages"
    )
    default_conf_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Default confidence threshold for detection"
    )
    model_load_timeout: float = Field(
        default=30.0,
        gt=0.0,
        description="Timeout in seconds for model loading"
    )
    history_update_interval: int = Field(
        default=10,
        gt=0,
        description="Update history every N calls"
    )


class LoggingConfig(BaseSettings):
    """Logging configuration for the service and submodules."""
    
    model_config = SettingsConfigDict(
        env_prefix="V1_LOGGING__",
        extra="ignore",
    )
    
    level: str = Field(
        default="INFO",
        description="Main logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )
    submodule_level: str = Field(
        default="WARNING",
        description="Logging level for submodules (screenshotanalysis, paddleocr)"
    )
    use_json: bool = Field(
        default=False,
        description="Use JSON structured logging format"
    )
    enable_request_logging: bool = Field(
        default=True,
        description="Enable request/response logging middleware"
    )
    
    def get_level(self) -> int:
        """Convert string level to logging constant."""
        return getattr(logging, self.level.upper(), logging.INFO)
    
    def get_submodule_level(self) -> int:
        """Convert string submodule level to logging constant."""
        return getattr(logging, self.submodule_level.upper(), logging.WARNING)


class V1Config(BaseSettings):
    """Main configuration for ChatCoach API v1."""
    
    model_config = SettingsConfigDict(
        env_prefix="V1_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Screenshot processing configuration
    screenshot: ScreenshotConfig = Field(default_factory=ScreenshotConfig)

    sign_secret: str = Field(
        default="",
        description="Secret used to validate request sign"
    )
    
    # Logging configuration
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    @classmethod
    def from_yaml(cls, config_path: str = "config.yaml") -> "V1Config":
        """
        Load configuration from YAML file with environment variable overrides.
        
        Args:
            config_path: Path to the YAML configuration file
            
        Returns:
            V1Config instance with loaded configuration
        """
        config_data = {}
        
        # Load from YAML file if it exists
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    yaml_data = yaml.safe_load(f) or {}
                    
                    # Extract v1-specific configuration
                    if 'v1' in yaml_data:
                        config_data = yaml_data['v1']
                    elif 'screenshot' in yaml_data or 'logging' in yaml_data:
                        # Support flat structure
                        config_data = yaml_data
            except Exception as e:
                logging.warning(f"Failed to load config from {config_path}: {e}")
        
        # Create config with YAML data
        if config_data:
            screenshot_data = config_data.get('screenshot', {})
            logging_data = config_data.get('logging', {})
            sign_secret = config_data.get('sign_secret', "")
            
            return cls(
                screenshot=ScreenshotConfig(**screenshot_data) if screenshot_data else ScreenshotConfig(),
                logging=LoggingConfig(**logging_data) if logging_data else LoggingConfig(),
                sign_secret=sign_secret,
            )
        
        # Return default config (will still load from env vars)
        return cls()
    
    def setup_logging(self) -> None:
        """
        Configure logging for the application and submodules.
        Sets up the main logger and configures submodule loggers.
        
        Requirements: 10.3, 10.4
        """
        # Import structured logging setup
        from app.api.v1.middleware import setup_structured_logging
        
        # Configure structured logging
        setup_structured_logging(
            level=self.logging.get_level(),
            use_json=self.logging.use_json
        )
         
        # Configure submodule loggers
        submodule_level = self.logging.get_submodule_level()
        for module_name in ["paddleocr", "paddle"]:
            logger = logging.getLogger(module_name)
            logger.setLevel(submodule_level)
             
            # Prevent propagation to avoid duplicate logs
            logger.propagate = False
        
        # Log configuration
        main_logger = logging.getLogger(__name__)
        main_logger.info(
            f"Logging configured: level={self.logging.level}, "
            f"submodule_level={self.logging.submodule_level}, "
            f"json={self.logging.use_json}, "
            f"request_logging={self.logging.enable_request_logging}"
        )


# Global v1 configuration instance
v1_settings: Optional[V1Config] = None


def get_v1_config() -> V1Config:
    """
    Get or create the global v1 configuration instance.
    
    Returns:
        V1Config instance
    """
    global v1_settings
    if v1_settings is None:
        v1_settings = V1Config.from_yaml()
        v1_settings.setup_logging()
    return v1_settings
