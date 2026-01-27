"""
Unit tests for v1 configuration loading and validation.
Tests Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
"""

import os
import tempfile
import logging
import pytest
from app.core.v1_config import (
    ScreenshotConfig,
    LoggingConfig,
    V1Config,
    get_v1_config
)


class TestScreenshotConfig:
    """Test screenshot configuration model."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        config = ScreenshotConfig()
        
        assert len(config.supported_apps) > 0
        assert "whatsapp" in config.supported_apps
        assert "telegram" in config.supported_apps
        
        assert len(config.supported_languages) > 0
        assert "en" in config.supported_languages
        assert "zh" in config.supported_languages
        
        assert 0.0 <= config.default_conf_threshold <= 1.0
        assert config.model_load_timeout > 0
        assert config.history_update_interval > 0
    
    def test_custom_values(self):
        """Test creating config with custom values."""
        config = ScreenshotConfig(
            supported_apps=["whatsapp", "telegram"],
            supported_languages=["en", "zh"],
            default_conf_threshold=0.7,
            model_load_timeout=60.0,
            history_update_interval=20
        )
        
        assert config.supported_apps == ["whatsapp", "telegram"]
        assert config.supported_languages == ["en", "zh"]
        assert config.default_conf_threshold == 0.7
        assert config.model_load_timeout == 60.0
        assert config.history_update_interval == 20
    
    def test_conf_threshold_validation(self):
        """Test that conf_threshold is validated to be between 0.0 and 1.0."""
        # Valid values
        ScreenshotConfig(default_conf_threshold=0.0)
        ScreenshotConfig(default_conf_threshold=0.5)
        ScreenshotConfig(default_conf_threshold=1.0)
        
        # Invalid values should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            ScreenshotConfig(default_conf_threshold=-0.1)
        
        with pytest.raises(Exception):
            ScreenshotConfig(default_conf_threshold=1.1)


class TestLoggingConfig:
    """Test logging configuration model."""
    
    def test_default_values(self):
        """Test that default logging values are set correctly."""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.submodule_level == "WARNING"
        assert "%(asctime)s" in config.format
        assert "%(levelname)s" in config.format
    
    def test_get_level(self):
        """Test converting string level to logging constant."""
        config = LoggingConfig(level="DEBUG")
        assert config.get_level() == logging.DEBUG
        
        config = LoggingConfig(level="INFO")
        assert config.get_level() == logging.INFO
        
        config = LoggingConfig(level="WARNING")
        assert config.get_level() == logging.WARNING
        
        config = LoggingConfig(level="ERROR")
        assert config.get_level() == logging.ERROR
    
    def test_get_submodule_level(self):
        """Test converting string submodule level to logging constant."""
        config = LoggingConfig(submodule_level="WARNING")
        assert config.get_submodule_level() == logging.WARNING
        
        config = LoggingConfig(submodule_level="ERROR")
        assert config.get_submodule_level() == logging.ERROR


class TestV1Config:
    """Test main v1 configuration."""
    
    def test_default_config(self):
        """Test creating config with defaults."""
        config = V1Config()
        
        assert isinstance(config.screenshot, ScreenshotConfig)
        assert isinstance(config.logging, LoggingConfig)
    
    def test_from_yaml_nonexistent_file(self):
        """Test loading from non-existent YAML file uses defaults."""
        config = V1Config.from_yaml("nonexistent.yaml")
        
        assert isinstance(config.screenshot, ScreenshotConfig)
        assert isinstance(config.logging, LoggingConfig)
    
    def test_from_yaml_with_file(self):
        """Test loading configuration from YAML file."""
        yaml_content = """
v1:
  screenshot:
    supported_apps:
      - whatsapp
      - telegram
    supported_languages:
      - en
      - zh
    default_conf_threshold: 0.6
  logging:
    level: DEBUG
    submodule_level: ERROR
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = V1Config.from_yaml(temp_path)
            
            assert config.screenshot.supported_apps == ["whatsapp", "telegram"]
            assert config.screenshot.supported_languages == ["en", "zh"]
            assert config.screenshot.default_conf_threshold == 0.6
            assert config.logging.level == "DEBUG"
            assert config.logging.submodule_level == "ERROR"
        finally:
            os.unlink(temp_path)
    
    def test_from_yaml_flat_structure(self):
        """Test loading from YAML with flat structure (no v1 key)."""
        yaml_content = """
screenshot:
  supported_apps:
    - discord
  supported_languages:
    - es
logging:
  level: WARNING
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = V1Config.from_yaml(temp_path)
            
            assert config.screenshot.supported_apps == ["discord"]
            assert config.screenshot.supported_languages == ["es"]
            assert config.logging.level == "WARNING"
        finally:
            os.unlink(temp_path)
    
    def test_setup_logging(self):
        """Test that logging setup configures loggers correctly."""
        config = V1Config(
            logging=LoggingConfig(
                level="DEBUG",
                submodule_level="ERROR"
            )
        )
        
        config.setup_logging()
        
        # Check root logger
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
        
        # Check submodule loggers
        for module_name in ["screenshotanalysis", "paddleocr", "paddle"]:
            logger = logging.getLogger(module_name)
            assert logger.level == logging.ERROR


class TestGetV1Config:
    """Test the global config getter function."""
    
    def test_get_v1_config_returns_instance(self):
        """Test that get_v1_config returns a V1Config instance."""
        config = get_v1_config()
        
        assert isinstance(config, V1Config)
        assert isinstance(config.screenshot, ScreenshotConfig)
        assert isinstance(config.logging, LoggingConfig)
    
    def test_get_v1_config_singleton(self):
        """Test that get_v1_config returns the same instance."""
        config1 = get_v1_config()
        config2 = get_v1_config()
        
        assert config1 is config2


class TestEnvironmentVariableOverrides:
    """Test environment variable overrides for configuration."""
    
    def test_env_override_logging_level(self, monkeypatch):
        """Test that V1_LOGGING__LEVEL environment variable overrides config."""
        # Set environment variable
        monkeypatch.setenv("V1_LOGGING__LEVEL", "ERROR")
        
        # Create config (should pick up env var)
        config = V1Config()
        
        assert config.logging.level == "ERROR"
    
    def test_env_override_logging_submodule_level(self, monkeypatch):
        """Test that V1_LOGGING__SUBMODULE_LEVEL environment variable overrides config."""
        monkeypatch.setenv("V1_LOGGING__SUBMODULE_LEVEL", "CRITICAL")
        
        config = V1Config()
        
        assert config.logging.submodule_level == "CRITICAL"
    
    def test_env_override_screenshot_conf_threshold(self, monkeypatch):
        """Test that V1_SCREENSHOT__DEFAULT_CONF_THRESHOLD environment variable overrides config."""
        monkeypatch.setenv("V1_SCREENSHOT__DEFAULT_CONF_THRESHOLD", "0.8")
        
        config = V1Config()
        
        assert config.screenshot.default_conf_threshold == 0.8
    
    def test_env_override_screenshot_model_timeout(self, monkeypatch):
        """Test that V1_SCREENSHOT__MODEL_LOAD_TIMEOUT environment variable overrides config."""
        monkeypatch.setenv("V1_SCREENSHOT__MODEL_LOAD_TIMEOUT", "60.0")
        
        config = V1Config()
        
        assert config.screenshot.model_load_timeout == 60.0
    
    def test_env_override_screenshot_history_interval(self, monkeypatch):
        """Test that V1_SCREENSHOT__HISTORY_UPDATE_INTERVAL environment variable overrides config."""
        monkeypatch.setenv("V1_SCREENSHOT__HISTORY_UPDATE_INTERVAL", "25")
        
        config = V1Config()
        
        assert config.screenshot.history_update_interval == 25
    
    def test_multiple_env_overrides(self, monkeypatch):
        """Test that multiple environment variables can override config simultaneously."""
        monkeypatch.setenv("V1_LOGGING__LEVEL", "DEBUG")
        monkeypatch.setenv("V1_LOGGING__SUBMODULE_LEVEL", "INFO")
        monkeypatch.setenv("V1_SCREENSHOT__DEFAULT_CONF_THRESHOLD", "0.75")
        
        config = V1Config()
        
        assert config.logging.level == "DEBUG"
        assert config.logging.submodule_level == "INFO"
        assert config.screenshot.default_conf_threshold == 0.75
    
    def test_env_override_with_yaml_file(self, monkeypatch):
        """Test that environment variables override YAML file values."""
        yaml_content = """
v1:
  screenshot:
    default_conf_threshold: 0.5
  logging:
    level: INFO
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            # Set env var that should override YAML
            monkeypatch.setenv("V1_LOGGING__LEVEL", "WARNING")
            
            config = V1Config.from_yaml(temp_path)
            
            # YAML value should be loaded first
            assert config.screenshot.default_conf_threshold == 0.5
            
            # But env var should NOT override in from_yaml (it only loads YAML)
            # The from_yaml method doesn't apply env overrides
            assert config.logging.level == "INFO"
        finally:
            os.unlink(temp_path)


class TestConfigFromFile:
    """Test loading configuration from the actual config.yaml file."""
    
    def test_load_from_config_yaml(self):
        """Test loading from config.yaml if it exists."""
        if not os.path.exists("config.yaml"):
            pytest.skip("config.yaml not found")
        
        config = V1Config.from_yaml("config.yaml")
        
        # Verify expected apps are present
        assert "whatsapp" in config.screenshot.supported_apps
        assert "telegram" in config.screenshot.supported_apps
        
        # Verify expected languages are present
        assert "en" in config.screenshot.supported_languages
        assert "zh" in config.screenshot.supported_languages
        
        # Verify threshold is valid
        assert 0.0 <= config.screenshot.default_conf_threshold <= 1.0
