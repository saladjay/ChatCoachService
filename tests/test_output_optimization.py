"""Unit tests for Phase 3: Output Optimization.

Tests reasoning control, configuration management, and length constraints.
"""

import pytest
import os
from unittest.mock import Mock, AsyncMock, patch

from app.core.config import PromptConfig
from app.services.prompt_assembler import PromptAssembler, REPLY_LENGTH_CONSTRAINTS
from app.services.llm_adapter import LLMCall
from app.services.reply_generator_impl import LLMAdapterReplyGenerator
from app.models.schemas import (
    ReplyGenerationInput,
    ContextResult,
    SceneAnalysisResult,
    PersonaSnapshot,
)


class TestPromptConfig:
    """Test PromptConfig class."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = PromptConfig()
        
        assert config.include_reasoning is False
        assert config.max_reply_tokens == 100
        assert config.use_compact_schemas is True
    
    def test_from_env_defaults(self):
        """Test loading from environment with defaults."""
        # Clear environment variables
        for key in ["PROMPT_INCLUDE_REASONING", "PROMPT_MAX_REPLY_TOKENS", "PROMPT_USE_COMPACT_SCHEMAS"]:
            if key in os.environ:
                del os.environ[key]
        
        config = PromptConfig.from_env()
        
        assert config.include_reasoning is False
        assert config.max_reply_tokens == 100
        assert config.use_compact_schemas is True
    
    def test_from_env_custom_values(self):
        """Test loading custom values from environment."""
        os.environ["PROMPT_INCLUDE_REASONING"] = "true"
        os.environ["PROMPT_MAX_REPLY_TOKENS"] = "150"
        os.environ["PROMPT_USE_COMPACT_SCHEMAS"] = "false"
        
        config = PromptConfig.from_env()
        
        assert config.include_reasoning is True
        assert config.max_reply_tokens == 150
        assert config.use_compact_schemas is False
        
        # Cleanup
        del os.environ["PROMPT_INCLUDE_REASONING"]
        del os.environ["PROMPT_MAX_REPLY_TOKENS"]
        del os.environ["PROMPT_USE_COMPACT_SCHEMAS"]
    
    def test_from_env_invalid_tokens_clamped(self):
        """Test that invalid token values are clamped to valid range."""
        # Test too high
        os.environ["PROMPT_MAX_REPLY_TOKENS"] = "1000"
        config = PromptConfig.from_env()
        assert 20 <= config.max_reply_tokens <= 500
        
        # Test too low
        os.environ["PROMPT_MAX_REPLY_TOKENS"] = "5"
        config = PromptConfig.from_env()
        assert 20 <= config.max_reply_tokens <= 500
        
        # Cleanup
        del os.environ["PROMPT_MAX_REPLY_TOKENS"]
    
    def test_from_env_invalid_tokens_uses_default(self):
        """Test that invalid token strings use default value."""
        os.environ["PROMPT_MAX_REPLY_TOKENS"] = "invalid"
        config = PromptConfig.from_env()
        assert config.max_reply_tokens == 100
        
        # Cleanup
        del os.environ["PROMPT_MAX_REPLY_TOKENS"]


class TestReasoningControl:
    """Test reasoning control in prompt assembly."""
    
    @pytest.fixture
    def mock_user_profile_service(self):
        """Create mock user profile service."""
        service = Mock()
        service.get_profile_for_llm = AsyncMock(return_value={
            "style": "casual",
            "pacing": "normal",
            "risk_tolerance": "medium"
        })
        return service
    
    @pytest.mark.asyncio
    async def test_output_schema_with_reasoning(self, mock_user_profile_service):
        """Test output schema instruction includes reasoning when enabled."""
        assembler = PromptAssembler(
            mock_user_profile_service,
            use_compact_prompt=True,
            use_compact_v2=True,
            include_reasoning=True
        )
        
        instruction = assembler._build_output_schema_instruction(include_reasoning=True)
        
        assert "reasoning" in instruction.lower()
        assert '["<reply_text>", "<strategy_code>", "<reasoning>"]' in instruction
    
    @pytest.mark.asyncio
    async def test_output_schema_without_reasoning(self, mock_user_profile_service):
        """Test output schema instruction excludes reasoning when disabled."""
        assembler = PromptAssembler(
            mock_user_profile_service,
            use_compact_prompt=True,
            use_compact_v2=True,
            include_reasoning=False
        )
        
        instruction = assembler._build_output_schema_instruction(include_reasoning=False)
        
        assert "exclude reasoning" in instruction.lower()
        assert '["<reply_text>", "<strategy_code>"]' in instruction
        assert "<reasoning>" not in instruction
    
    @pytest.mark.asyncio
    async def test_prompt_includes_output_instruction(self, mock_user_profile_service):
        """Test that assembled prompt includes output schema instruction."""
        assembler = PromptAssembler(
            mock_user_profile_service,
            use_compact_prompt=True,
            use_compact_v2=True,
            include_reasoning=False
        )
        
        # Create test input
        input_data = ReplyGenerationInput(
            user_id="test_user",
            prompt="test",
            quality="normal",
            context=ContextResult(
                conversation_summary="Test conversation",
                emotion_state="positive",
                current_intimacy_level=50,
                conversation=[]
            ),
            scene=SceneAnalysisResult(
                relationship_state="propulsion",
                scenario="BALANCED",
                intimacy_level=60,
                recommended_scenario="BALANCED",
                recommended_strategies=["emotional_resonance"]
            ),
            persona=PersonaSnapshot(
                style="casual",
                pacing="normal",
                risk_tolerance="medium",
                confidence=0.8,
                prompt=""
            ),
            language="en"
        )
        
        prompt = await assembler.assemble_reply_prompt(input_data)
        
        assert "Output Format" in prompt
        assert "Exclude reasoning" in prompt


class TestLengthConstraints:
    """Test length constraints by quality tier."""
    
    def test_length_constraints_defined(self):
        """Test that length constraints are defined for all quality tiers."""
        assert "cheap" in REPLY_LENGTH_CONSTRAINTS
        assert "normal" in REPLY_LENGTH_CONSTRAINTS
        assert "premium" in REPLY_LENGTH_CONSTRAINTS
    
    def test_length_constraints_structure(self):
        """Test that length constraints have required fields."""
        for quality, constraint in REPLY_LENGTH_CONSTRAINTS.items():
            assert "max_tokens" in constraint
            assert "guidance" in constraint
            assert isinstance(constraint["max_tokens"], int)
            assert isinstance(constraint["guidance"], str)
    
    def test_length_constraints_ordering(self):
        """Test that token limits increase with quality tier."""
        cheap_tokens = REPLY_LENGTH_CONSTRAINTS["cheap"]["max_tokens"]
        normal_tokens = REPLY_LENGTH_CONSTRAINTS["normal"]["max_tokens"]
        premium_tokens = REPLY_LENGTH_CONSTRAINTS["premium"]["max_tokens"]
        
        assert cheap_tokens < normal_tokens < premium_tokens
    
    def test_length_constraints_values(self):
        """Test specific token limit values."""
        assert REPLY_LENGTH_CONSTRAINTS["cheap"]["max_tokens"] == 50
        assert REPLY_LENGTH_CONSTRAINTS["normal"]["max_tokens"] == 100
        assert REPLY_LENGTH_CONSTRAINTS["premium"]["max_tokens"] == 200


class TestLLMCallMaxTokens:
    """Test max_tokens parameter in LLMCall."""
    
    def test_llm_call_with_max_tokens(self):
        """Test creating LLMCall with max_tokens."""
        call = LLMCall(
            task_type="generation",
            prompt="test prompt",
            quality="normal",
            user_id="test_user",
            max_tokens=100
        )
        
        assert call.max_tokens == 100
    
    def test_llm_call_without_max_tokens(self):
        """Test creating LLMCall without max_tokens (defaults to None)."""
        call = LLMCall(
            task_type="generation",
            prompt="test prompt",
            quality="normal",
            user_id="test_user"
        )
        
        assert call.max_tokens is None
    
    def test_llm_call_max_tokens_by_quality(self):
        """Test that max_tokens can be set based on quality tier."""
        for quality in ["cheap", "normal", "premium"]:
            constraint = REPLY_LENGTH_CONSTRAINTS[quality]
            call = LLMCall(
                task_type="generation",
                prompt="test",
                quality=quality,
                max_tokens=constraint["max_tokens"]
            )
            
            assert call.max_tokens == constraint["max_tokens"]


class TestReplyGeneratorIntegration:
    """Test reply generator with output optimization."""
    
    @pytest.fixture
    def mock_llm_adapter(self):
        """Create mock LLM adapter."""
        from app.models.schemas import LLMResult
        
        adapter = Mock()
        adapter.call = AsyncMock(return_value=LLMResult(
            text='{"r":[["Hello!","emotional_resonance"]],"adv":"Keep it light"}',
            provider="dashscope",
            model="qwen-flash",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001
        ))
        return adapter
    
    @pytest.fixture
    def mock_user_profile_service(self):
        """Create mock user profile service."""
        service = Mock()
        service.get_profile_for_llm = AsyncMock(return_value={
            "style": "casual",
            "pacing": "normal",
            "risk_tolerance": "medium"
        })
        return service
    
    @pytest.mark.asyncio
    async def test_reply_generator_uses_prompt_config(self, mock_llm_adapter, mock_user_profile_service):
        """Test that reply generator uses PromptConfig."""
        config = PromptConfig(
            include_reasoning=False,
            max_reply_tokens=150,
            use_compact_schemas=True
        )
        
        generator = LLMAdapterReplyGenerator(
            llm_adapter=mock_llm_adapter,
            user_profile_service=mock_user_profile_service,
            prompt_config=config
        )
        
        assert generator.prompt_config.include_reasoning is False
        assert generator.prompt_config.max_reply_tokens == 150
    
    @pytest.mark.asyncio
    async def test_reply_generator_sets_max_tokens(self, mock_llm_adapter, mock_user_profile_service):
        """Test that reply generator sets max_tokens in LLMCall."""
        config = PromptConfig(
            include_reasoning=False,
            max_reply_tokens=150,
            use_compact_schemas=True
        )
        
        generator = LLMAdapterReplyGenerator(
            llm_adapter=mock_llm_adapter,
            user_profile_service=mock_user_profile_service,
            prompt_config=config
        )
        
        input_data = ReplyGenerationInput(
            user_id="test_user",
            prompt="test",
            quality="normal",
            context=ContextResult(
                conversation_summary="Test",
                emotion_state="positive",
                current_intimacy_level=50,
                conversation=[]
            ),
            scene=SceneAnalysisResult(
                relationship_state="propulsion",
                scenario="BALANCED",
                intimacy_level=60,
                recommended_scenario="BALANCED",
                recommended_strategies=[]
            ),
            persona=PersonaSnapshot(
                style="casual",
                pacing="normal",
                risk_tolerance="medium",
                confidence=0.8,
                prompt=""
            )
        )
        
        await generator.generate_reply(input_data)
        
        # Verify LLMCall was created with max_tokens
        call_args = mock_llm_adapter.call.call_args[0][0]
        assert call_args.max_tokens == 150


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""
    
    @pytest.fixture
    def mock_user_profile_service(self):
        """Create mock user profile service."""
        service = Mock()
        service.get_profile_for_llm = AsyncMock(return_value={
            "style": "casual",
            "pacing": "normal",
            "risk_tolerance": "medium"
        })
        return service
    
    def test_prompt_assembler_without_reasoning_param(self, mock_user_profile_service):
        """Test PromptAssembler works without include_reasoning parameter."""
        # Should use default (False)
        assembler = PromptAssembler(
            mock_user_profile_service,
            use_compact_prompt=True,
            use_compact_v2=True
        )
        
        assert assembler.include_reasoning is False
    
    def test_llm_call_without_max_tokens_param(self):
        """Test LLMCall works without max_tokens parameter."""
        call = LLMCall(
            task_type="generation",
            prompt="test",
            quality="normal",
            user_id="test_user"
        )
        
        assert call.max_tokens is None
    
    @pytest.mark.asyncio
    async def test_reply_generator_without_prompt_config(self, mock_user_profile_service):
        """Test reply generator works without prompt_config parameter."""
        from app.models.schemas import LLMResult
        
        mock_adapter = Mock()
        mock_adapter.call = AsyncMock(return_value=LLMResult(
            text='{"r":[["Hi","emotional_resonance"]],"adv":"Test"}',
            provider="test",
            model="test",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001
        ))
        
        # Should use default config from environment
        generator = LLMAdapterReplyGenerator(
            llm_adapter=mock_adapter,
            user_profile_service=mock_user_profile_service
        )
        
        assert generator.prompt_config is not None
        assert isinstance(generator.prompt_config, PromptConfig)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
