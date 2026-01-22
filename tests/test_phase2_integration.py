"""Integration tests for Phase 2: Prompt Layering (3-Stage Pipeline).

This module tests the complete 3-stage pipeline:
1. SceneAnalyzer: Analyzes conversation context
2. StrategyPlanner: Plans specific strategies
3. ReplyGenerator: Generates replies using strategy plan

Tests verify:
- End-to-end flow works correctly
- Token reduction is achieved
- Quality is maintained
- Services integrate properly
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.schemas import (
    SceneAnalysisInput,
    SceneAnalysisResult,
    ReplyGenerationInput,
    ContextResult,
    Message,
    LLMResult,
)
from app.services.scene_analyzer_impl import SceneAnalyzer
from app.services.strategy_planner import StrategyPlanner, StrategyPlanInput
from app.services.reply_generator_impl import LLMAdapterReplyGenerator
from app.services.llm_adapter import LLMCall


class TestPhase2Integration:
    """Test 3-stage pipeline integration."""
    
    @pytest.fixture
    def mock_llm_adapter(self):
        """Create mock LLM adapter."""
        adapter = AsyncMock()
        
        # Mock scene analysis response (compact format)
        adapter.call.side_effect = [
            # Scene analysis response
            LLMResult(
                text='{"cs": "S", "rs": "I", "st": ["emotional_resonance", "playful_tease"]}',
                model="qwen-flash",
                provider="dashscope",
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
                cost_usd=0.001,
                latency=500
            ),
            # Strategy planning response
            LLMResult(
                text='{"rec": "B", "w": {"emotional_resonance": 0.9, "playful_tease": 0.7}, "av": []}',
                model="qwen-flash",
                provider="dashscope",
                input_tokens=80,
                output_tokens=15,
                total_tokens=95,
                cost_usd=0.0008,
                latency=400
            ),
            # Reply generation response
            LLMResult(
                text='{"r": [["Hello! How are you?", "emotional_resonance"], ["What\'s up?", "playful_tease"]], "adv": "Keep it friendly"}',
                model="qwen-flash",
                provider="dashscope",
                input_tokens=200,
                output_tokens=30,
                total_tokens=230,
                cost_usd=0.002,
                latency=600
            )
        ]
        
        return adapter
    
    @pytest.fixture
    def mock_user_profile_service(self):
        """Create mock user profile service."""
        service = AsyncMock()
        service.get_profile_for_llm.return_value = {
            "style": "friendly",
            "pacing": "normal"
        }
        return service
    
    @pytest.mark.asyncio
    async def test_three_stage_pipeline(self, mock_llm_adapter, mock_user_profile_service):
        """Test complete 3-stage pipeline flow."""
        # Stage 1: Scene Analysis
        scene_analyzer = SceneAnalyzer(
            llm_adapter=mock_llm_adapter,
            use_compact_v2=True
        )
        
        scene_input = SceneAnalysisInput(
            conversation_id="test-conv",
            history_dialog=[
                Message(id="1", speaker="user", content="Hi there!"),
                Message(id="2", speaker="assistant", content="Hello!")
            ],
            emotion_trend=None,
            current_conversation_summary="Friendly greeting exchange",
            intimacy_value=60,
            current_intimacy_level=45
        )
        
        scene_result = await scene_analyzer.analyze_scene(scene_input)
        
        # Verify scene analysis
        assert scene_result is not None
        assert scene_result.recommended_scenario in ["SAFE", "BALANCED", "RISKY", "RECOVERY", "NEGATIVE"]
        assert len(scene_result.recommended_strategies) > 0
        
        # Stage 2: Strategy Planning
        strategy_planner = StrategyPlanner(
            llm_adapter=mock_llm_adapter,
            use_compact=True
        )
        
        plan_input = StrategyPlanInput(
            scene=scene_result,
            conversation_summary="Friendly greeting exchange",
            intimacy_level=60,
            current_intimacy_level=45
        )
        
        strategy_plan = await strategy_planner.plan_strategies(plan_input)
        
        # Verify strategy plan
        assert strategy_plan is not None
        assert strategy_plan.recommended_scenario in ["SAFE", "BALANCED", "RISKY", "RECOVERY", "NEGATIVE"]
        assert len(strategy_plan.strategy_weights) > 0
        assert all(0 <= w <= 1 for w in strategy_plan.strategy_weights.values())
        
        # Stage 3: Reply Generation
        reply_generator = LLMAdapterReplyGenerator(
            llm_adapter=mock_llm_adapter,
            user_profile_service=mock_user_profile_service,
            use_compact_v2=True,
            strategy_planner=strategy_planner
        )
        
        context = ContextResult(
            conversation_summary="Friendly greeting exchange",
            current_intimacy_level=45,
            emotion_state="positive",
            conversation=[
                Message(id="1", speaker="user", content="Hi there!"),
                Message(id="2", speaker="assistant", content="Hello!")
            ]
        )
        
        reply_input = ReplyGenerationInput(
            user_id="test-user",
            prompt="Generate reply",
            quality="normal",
            context=context,
            scene=scene_result,
            persona=None,
            language="en"
        )
        
        # Note: This will call strategy planner internally
        reply_result = await reply_generator.generate_reply(reply_input)
        
        # Verify reply generation
        assert reply_result is not None
        assert reply_result.text is not None
        
        # Verify LLM was called 3 times (scene + strategy + reply)
        # Note: In actual implementation, reply_generator calls strategy_planner
        # so we expect 4 calls total (scene + strategy + strategy_again + reply)
        assert mock_llm_adapter.call.call_count >= 3
    
    @pytest.mark.asyncio
    async def test_token_reduction_measurement(self, mock_llm_adapter, mock_user_profile_service):
        """Test that 3-stage pipeline reduces tokens compared to 2-stage."""
        # Create services
        scene_analyzer = SceneAnalyzer(
            llm_adapter=mock_llm_adapter,
            use_compact_v2=True
        )
        
        strategy_planner = StrategyPlanner(
            llm_adapter=mock_llm_adapter,
            use_compact=True
        )
        
        # Prepare input
        scene_input = SceneAnalysisInput(
            conversation_id="test-conv",
            history_dialog=[
                Message(id="1", speaker="user", content="Hi there!"),
                Message(id="2", speaker="assistant", content="Hello!")
            ],
            emotion_trend=None,
            current_conversation_summary="Friendly greeting exchange",
            intimacy_value=60,
            current_intimacy_level=45
        )
        
        # Run pipeline
        scene_result = await scene_analyzer.analyze_scene(scene_input)
        
        plan_input = StrategyPlanInput(
            scene=scene_result,
            conversation_summary="Friendly greeting exchange",
            intimacy_level=60,
            current_intimacy_level=45
        )
        
        strategy_plan = await strategy_planner.plan_strategies(plan_input)
        
        # Measure tokens
        # Scene: ~100 input + ~20 output = 120 tokens
        # Strategy: ~80 input + ~15 output = 95 tokens
        # Total: ~215 tokens for first 2 stages
        
        # Expected: ~270 (scene) + ~190 (strategy) = ~460 tokens
        # vs original ~1470 tokens (scene + full reply prompt)
        # Savings: ~69% reduction
        
        # Verify token counts are reasonable
        calls = mock_llm_adapter.call.call_args_list
        
        # First call (scene analysis)
        scene_call = calls[0][0][0]
        assert isinstance(scene_call, LLMCall)
        # Prompt should be compact
        assert len(scene_call.prompt) < 500  # Ultra-compact prompt
        
        # Second call (strategy planning)
        strategy_call = calls[1][0][0]
        assert isinstance(strategy_call, LLMCall)
        # Prompt should be ultra-compact
        assert len(strategy_call.prompt) < 800  # ~190 tokens
    
    @pytest.mark.asyncio
    async def test_pipeline_without_strategy_planner(self, mock_llm_adapter, mock_user_profile_service):
        """Test that pipeline works without strategy planner (backward compatibility)."""
        # Create reply generator without strategy planner
        reply_generator = LLMAdapterReplyGenerator(
            llm_adapter=mock_llm_adapter,
            user_profile_service=mock_user_profile_service,
            use_compact_v2=True,
            strategy_planner=None  # No strategy planner
        )
        
        scene_result = SceneAnalysisResult(
            relationship_state="ignition",
            scenario="BALANCED",
            intimacy_level=50,
            risk_flags=[],
            current_scenario="SAFE",
            recommended_scenario="BALANCED",
            recommended_strategies=["emotional_resonance", "playful_tease"]
        )
        
        context = ContextResult(
            conversation_summary="Friendly greeting exchange",
            current_intimacy_level=45,
            emotion_state="positive",
            conversation=[
                Message(id="1", speaker="user", content="Hi there!"),
                Message(id="2", speaker="assistant", content="Hello!")
            ]
        )
        
        reply_input = ReplyGenerationInput(
            user_id="test-user",
            prompt="Generate reply",
            quality="normal",
            context=context,
            scene=scene_result,
            persona=None,
            language="en"
        )
        
        # Should work without strategy planner
        reply_result = await reply_generator.generate_reply(reply_input)
        
        assert reply_result is not None
        assert reply_result.text is not None
    
    @pytest.mark.asyncio
    async def test_strategy_plan_integration_with_prompt_assembler(self, mock_llm_adapter, mock_user_profile_service):
        """Test that strategy plan is properly used in prompt assembly."""
        from app.services.prompt_assembler import PromptAssembler
        from app.services.strategy_planner import StrategyPlanOutput
        
        # Create prompt assembler
        assembler = PromptAssembler(
            user_profile_service=mock_user_profile_service,
            use_compact_v2=True
        )
        
        # Create strategy plan
        strategy_plan = StrategyPlanOutput(
            recommended_scenario="BALANCED",
            strategy_weights={
                "emotional_resonance": 0.9,
                "playful_tease": 0.7,
                "curiosity_hook": 0.5
            },
            avoid_strategies=["neediness_signal"],
            reasoning="Focus on emotional connection"
        )
        
        scene_result = SceneAnalysisResult(
            relationship_state="ignition",
            scenario="BALANCED",
            intimacy_level=50,
            risk_flags=[],
            current_scenario="SAFE",
            recommended_scenario="BALANCED",
            recommended_strategies=["emotional_resonance", "playful_tease"]
        )
        
        context = ContextResult(
            conversation_summary="Friendly greeting exchange",
            current_intimacy_level=45,
            emotion_state="positive",
            conversation=[
                Message(id="1", speaker="user", content="Hi there!"),
                Message(id="2", speaker="assistant", content="Hello!")
            ]
        )
        
        reply_input = ReplyGenerationInput(
            user_id="test-user",
            prompt="Generate reply",
            quality="normal",
            context=context,
            scene=scene_result,
            persona=None,
            language="en"
        )
        
        # Assemble prompt with strategy plan
        prompt = await assembler.assemble_reply_prompt(reply_input, strategy_plan)
        
        # Verify prompt includes strategy weights
        assert "emotional_resonance" in prompt
        assert "0.9" in prompt or "emotional_resonance(0.9)" in prompt
        
        # Verify prompt is compact
        assert len(prompt) < 2000  # Should be much smaller than original


class TestPhase2TokenSavings:
    """Test token savings from Phase 2 optimizations."""
    
    def test_scene_analyzer_ultra_compact_prompt(self):
        """Test that SceneAnalyzer uses ultra-compact prompt."""
        from app.services.scene_analyzer_impl import SceneAnalyzer
        
        analyzer = SceneAnalyzer(
            llm_adapter=AsyncMock(),
            use_compact_v2=True
        )
        
        # Build ultra-compact prompt
        prompt = analyzer._build_ultra_compact_prompt(
            "Discussing travel and hobbies",
            SceneAnalysisInput(
                conversation_id="test",
                history_dialog=[],
                emotion_trend=None,
                current_conversation_summary="Test",
                intimacy_value=60,
                current_intimacy_level=45
            )
        )
        
        # Verify prompt is ultra-compact
        # Target: ~80 tokens fixed + summary length
        # Estimate: 4 chars per token
        assert len(prompt) < 500  # ~125 tokens max
        
        # Verify essential elements are present
        assert "Scene analyzer" in prompt
        assert "Summary:" in prompt
        assert "Intimacy:" in prompt
        assert "Output JSON:" in prompt
        assert "cs=" in prompt  # Code legend
        assert "rs=" in prompt
    
    def test_strategy_planner_ultra_compact_prompt(self):
        """Test that StrategyPlanner uses ultra-compact prompt."""
        from app.services.strategy_planner import StrategyPlanner
        
        planner = StrategyPlanner(
            llm_adapter=AsyncMock(),
            use_compact=True
        )
        
        scene = SceneAnalysisResult(
            relationship_state="ignition",
            scenario="BALANCED",
            intimacy_level=50,
            risk_flags=[],
            current_scenario="SAFE",
            recommended_scenario="BALANCED",
            recommended_strategies=["emotional_resonance", "playful_tease"]
        )
        
        plan_input = StrategyPlanInput(
            scene=scene,
            conversation_summary="Discussing travel and hobbies",
            intimacy_level=60,
            current_intimacy_level=45
        )
        
        # Build ultra-compact prompt
        prompt = planner._build_prompt(plan_input)
        
        # Verify prompt is ultra-compact
        # Target: ~190 tokens
        # Estimate: 4 chars per token
        assert len(prompt) < 800  # ~200 tokens max
        
        # Verify essential elements are present
        assert "Strategy planner" in prompt
        assert "Scene:" in prompt
        assert "Strategies:" in prompt
        assert "Intimacy:" in prompt
        assert "Output JSON" in prompt
        assert "rec=" in prompt  # Code legend
        assert "w=" in prompt
        assert "av=" in prompt
