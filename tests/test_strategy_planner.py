"""Tests for StrategyPlanner service.

This module tests the strategy planning functionality including:
- Prompt building
- Response parsing
- Compact format handling
- Fallback logic
"""

import pytest
from unittest.mock import AsyncMock, Mock

from app.services.strategy_planner import (
    StrategyPlanner,
    StrategyPlanInput,
    StrategyPlanOutput
)
from app.models.schemas import SceneAnalysisResult, LLMResult


class TestStrategyPlannerPromptBuilding:
    """Test prompt building for strategy planning."""
    
    def test_build_compact_prompt(self):
        """Test building compact strategy planning prompt."""
        # Create mock scene analysis
        scene = SceneAnalysisResult(
            relationship_state="ignition",
            scenario="BALANCED",
            intimacy_level=50,
            risk_flags=[],
            current_scenario="SAFE",
            recommended_scenario="BALANCED",
            recommended_strategies=["playful_tease", "emotional_resonance", "curiosity_hook"]
        )
        
        # Create input
        input_data = StrategyPlanInput(
            scene=scene,
            conversation_summary="Discussing travel and hobbies",
            intimacy_level=60,
            current_intimacy_level=45
        )
        
        # Create planner
        planner = StrategyPlanner(
            llm_adapter=Mock(),
            use_compact=True
        )
        
        # Build prompt
        prompt = planner._build_prompt(input_data)
        
        # Verify prompt contains key information
        assert "BALANCED" in prompt
        assert "playful_tease" in prompt
        assert "60" in prompt  # target intimacy
        assert "45" in prompt  # current intimacy
        assert "rec" in prompt  # compact field name
        assert "w" in prompt  # weights field
        
        # Verify prompt is compact (target ~190 tokens, ~760 chars)
        assert len(prompt) < 1000, f"Prompt too long: {len(prompt)} chars"
    
    def test_build_standard_prompt(self):
        """Test building standard (non-compact) prompt."""
        scene = SceneAnalysisResult(
            relationship_state="ignition",
            scenario="BALANCED",
            intimacy_level=50,
            risk_flags=[],
            current_scenario="SAFE",
            recommended_scenario="BALANCED",
            recommended_strategies=["playful_tease"]
        )
        
        input_data = StrategyPlanInput(
            scene=scene,
            conversation_summary="Test conversation",
            intimacy_level=60,
            current_intimacy_level=45
        )
        
        planner = StrategyPlanner(
            llm_adapter=Mock(),
            use_compact=False
        )
        
        prompt = planner._build_prompt(input_data)
        
        # Verify standard format
        assert "recommended_scenario" in prompt
        assert "strategy_weights" in prompt
        assert "avoid_strategies" in prompt


class TestStrategyPlannerParsing:
    """Test response parsing for strategy planning."""
    
    def test_parse_compact_response(self):
        """Test parsing compact strategy plan response."""
        response_json = """
        {
            "rec": "B",
            "w": {
                "playful_tease": 0.9,
                "emotional_resonance": 0.8,
                "curiosity_hook": 0.7
            },
            "av": ["neediness_signal", "validation_seeking"]
        }
        """
        
        scene = SceneAnalysisResult(
            relationship_state="ignition",
            scenario="BALANCED",
            intimacy_level=50,
            risk_flags=[],
            current_scenario="SAFE",
            recommended_scenario="BALANCED",
            recommended_strategies=["playful_tease"]
        )
        
        input_data = StrategyPlanInput(
            scene=scene,
            conversation_summary="Test",
            intimacy_level=60,
            current_intimacy_level=45
        )
        
        planner = StrategyPlanner(
            llm_adapter=Mock(),
            use_compact=True
        )
        
        result = planner._parse_response(response_json, input_data)
        
        assert isinstance(result, StrategyPlanOutput)
        assert result.recommended_scenario == "BALANCED"
        assert len(result.strategy_weights) == 3
        assert result.strategy_weights["playful_tease"] == 0.9
        assert len(result.avoid_strategies) == 2
        assert "neediness_signal" in result.avoid_strategies
    
    def test_parse_compact_response_with_markdown(self):
        """Test parsing compact response wrapped in markdown."""
        response_json = """
        ```json
        {
            "rec": "R",
            "w": {"sexual_hint": 0.9},
            "av": ["validation_seeking"]
        }
        ```
        """
        
        scene = SceneAnalysisResult(
            relationship_state="propulsion",
            scenario="RISKY",
            intimacy_level=75,
            risk_flags=[],
            current_scenario="BALANCED",
            recommended_scenario="RISKY",
            recommended_strategies=["sexual_hint"]
        )
        
        input_data = StrategyPlanInput(
            scene=scene,
            conversation_summary="Test",
            intimacy_level=80,
            current_intimacy_level=75
        )
        
        planner = StrategyPlanner(
            llm_adapter=Mock(),
            use_compact=True
        )
        
        result = planner._parse_response(response_json, input_data)
        
        assert result.recommended_scenario == "RISKY"
        assert "sexual_hint" in result.strategy_weights
    
    def test_parse_standard_response(self):
        """Test parsing standard (non-compact) response."""
        response_json = """
        {
            "recommended_scenario": "BALANCED",
            "strategy_weights": {
                "playful_tease": 0.9,
                "emotional_resonance": 0.8
            },
            "avoid_strategies": ["neediness_signal"]
        }
        """
        
        scene = SceneAnalysisResult(
            relationship_state="ignition",
            scenario="BALANCED",
            intimacy_level=50,
            risk_flags=[],
            current_scenario="SAFE",
            recommended_scenario="BALANCED",
            recommended_strategies=["playful_tease"]
        )
        
        input_data = StrategyPlanInput(
            scene=scene,
            conversation_summary="Test",
            intimacy_level=60,
            current_intimacy_level=45
        )
        
        planner = StrategyPlanner(
            llm_adapter=Mock(),
            use_compact=False
        )
        
        result = planner._parse_response(response_json, input_data)
        
        assert result.recommended_scenario == "BALANCED"
        assert len(result.strategy_weights) == 2
        assert result.strategy_weights["playful_tease"] == 0.9
    
    def test_parse_invalid_response_fallback(self):
        """Test fallback logic when parsing fails."""
        invalid_json = "not a json"
        
        scene = SceneAnalysisResult(
            relationship_state="ignition",
            scenario="BALANCED",
            intimacy_level=50,
            risk_flags=[],
            current_scenario="SAFE",
            recommended_scenario="BALANCED",
            recommended_strategies=["playful_tease", "emotional_resonance", "curiosity_hook"]
        )
        
        input_data = StrategyPlanInput(
            scene=scene,
            conversation_summary="Test",
            intimacy_level=60,
            current_intimacy_level=45
        )
        
        planner = StrategyPlanner(
            llm_adapter=Mock(),
            use_compact=True
        )
        
        result = planner._parse_response(invalid_json, input_data)
        
        # Should use fallback logic
        assert isinstance(result, StrategyPlanOutput)
        assert result.recommended_scenario == "BALANCED"
        assert len(result.strategy_weights) == 3
        assert result.strategy_weights["playful_tease"] == 1.0
        assert result.strategy_weights["emotional_resonance"] == 0.9
        assert result.strategy_weights["curiosity_hook"] == 0.8


class TestStrategyPlannerIntegration:
    """Test strategy planner integration."""
    
    @pytest.mark.asyncio
    async def test_plan_strategies_compact(self):
        """Test full strategy planning flow with compact format."""
        # Mock LLM adapter
        mock_adapter = AsyncMock()
        mock_adapter.call = AsyncMock(return_value=LLMResult(
            text='{"rec": "B", "w": {"playful_tease": 0.9}, "av": []}',
            model="qwen-flash",
            provider="dashscope",
            input_tokens=50,
            output_tokens=20,
            cost_usd=0.001
        ))
        
        # Create planner
        planner = StrategyPlanner(
            llm_adapter=mock_adapter,
            use_compact=True
        )
        
        # Create input
        scene = SceneAnalysisResult(
            relationship_state="ignition",
            scenario="BALANCED",
            intimacy_level=50,
            risk_flags=[],
            current_scenario="SAFE",
            recommended_scenario="BALANCED",
            recommended_strategies=["playful_tease"]
        )
        
        input_data = StrategyPlanInput(
            scene=scene,
            conversation_summary="Discussing travel",
            intimacy_level=60,
            current_intimacy_level=45
        )
        
        # Plan strategies
        result = await planner.plan_strategies(input_data)
        
        # Verify result
        assert isinstance(result, StrategyPlanOutput)
        assert result.recommended_scenario == "BALANCED"
        assert "playful_tease" in result.strategy_weights
        
        # Verify LLM was called
        mock_adapter.call.assert_called_once()
        call_args = mock_adapter.call.call_args[0][0]
        assert call_args.task_type == "strategy_planning"
        assert "rec" in call_args.prompt  # Compact format


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
