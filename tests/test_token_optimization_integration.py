"""Integration tests for token optimization (Phase 1).

This module tests the end-to-end flow of compact schema usage:
1. SceneAnalyzer outputs compact JSON
2. SchemaExpander expands to full schema
3. ReplyGenerator uses compact prompts and outputs
4. Token savings are measured and validated
"""

import pytest
import json
from app.services.schema_expander import SchemaExpander, parse_and_expand_scene_analysis, parse_and_expand_reply_generation
from app.models.schemas_compact import SceneAnalysisCompact, ReplyGenerationCompact
from app.models.schemas import SceneAnalysisResult


class TestSceneAnalysisIntegration:
    """Test SceneAnalyzer compact mode integration."""
    
    def test_parse_compact_scene_analysis(self):
        """Test parsing compact scene analysis JSON."""
        compact_json = """
        {
            "rs": "I",
            "scn": "B",
            "il": 50,
            "rf": [],
            "cs": "S",
            "rsc": "B",
            "rst": ["playful_tease", "emotional_resonance", "curiosity_hook"],
            "tone": "P"
        }
        """
        
        result = parse_and_expand_scene_analysis(compact_json)
        
        assert isinstance(result, SceneAnalysisResult)
        assert result.relationship_state == "ignition"
        assert result.scenario == "BALANCED"
        assert result.intimacy_level == 50
        assert result.current_scenario == "SAFE"
        assert result.recommended_scenario == "BALANCED"
        assert len(result.recommended_strategies) == 3
        assert "playful_tease" in result.recommended_strategies
    
    def test_parse_compact_scene_analysis_with_markdown(self):
        """Test parsing compact JSON wrapped in markdown code block."""
        compact_json = """
        ```json
        {
            "rs": "P",
            "scn": "R",
            "il": 75,
            "rf": ["high_risk"],
            "cs": "B",
            "rsc": "R",
            "rst": ["sexual_hint", "dominant_lead"]
        }
        ```
        """
        
        result = parse_and_expand_scene_analysis(compact_json)
        
        assert result.relationship_state == "propulsion"
        assert result.scenario == "RISKY"
        assert result.intimacy_level == 75
        assert len(result.recommended_strategies) == 2
    
    def test_parse_invalid_compact_json(self):
        """Test error handling for invalid JSON."""
        invalid_json = "not a json"
        
        with pytest.raises(ValueError):
            parse_and_expand_scene_analysis(invalid_json)


class TestReplyGenerationIntegration:
    """Test ReplyGenerator compact mode integration."""
    
    def test_parse_compact_reply_generation(self):
        """Test parsing compact reply generation JSON."""
        compact_json = """
        {
            "r": [
                ["Hey! How's your day going?", "emotional_resonance"],
                ["I noticed you mentioned travel earlier", "curiosity_hook"],
                ["That sounds interesting! Tell me more", "playful_tease"]
            ],
            "adv": "Keep the conversation light and engaging"
        }
        """
        
        result = parse_and_expand_reply_generation(compact_json)
        
        assert "replies" in result
        assert "overall_advice" in result
        assert len(result["replies"]) == 3
        
        # Check first reply
        reply1 = result["replies"][0]
        assert reply1["text"] == "Hey! How's your day going?"
        assert reply1["strategy"] == "emotional_resonance"
        assert reply1["reasoning"] == ""  # No reasoning in compact mode
        
        # Check advice
        assert result["overall_advice"] == "Keep the conversation light and engaging"
    
    def test_parse_compact_reply_with_reasoning(self):
        """Test parsing compact reply with optional reasoning."""
        compact_json = """
        {
            "r": [
                ["Hello!", "emotional_resonance", "Start with warmth"],
                ["How are you?", "curiosity_hook", "Show interest"]
            ],
            "adv": "Be friendly"
        }
        """
        
        result = parse_and_expand_reply_generation(compact_json)
        
        assert len(result["replies"]) == 2
        assert result["replies"][0]["reasoning"] == "Start with warmth"
        assert result["replies"][1]["reasoning"] == "Show interest"
    
    def test_parse_compact_reply_minimal(self):
        """Test parsing minimal compact reply (text only)."""
        compact_json = """
        {
            "r": [
                ["Hello!"],
                ["How are you?"]
            ],
            "adv": ""
        }
        """
        
        result = parse_and_expand_reply_generation(compact_json)
        
        assert len(result["replies"]) == 2
        assert result["replies"][0]["text"] == "Hello!"
        assert result["replies"][0]["strategy"] == ""
        assert result["replies"][0]["reasoning"] == ""


class TestTokenSavingsIntegration:
    """Test token savings in integrated flow."""
    
    def test_scene_analysis_token_savings(self):
        """Test token savings for scene analysis."""
        # Verbose output
        verbose_json = {
            "relationship_state": "ignition",
            "scenario": "BALANCED",
            "intimacy_level": 50,
            "risk_flags": [],
            "current_scenario": "SAFE",
            "recommended_scenario": "BALANCED",
            "recommended_strategies": ["playful_tease", "emotional_resonance", "curiosity_hook"]
        }
        verbose_str = json.dumps(verbose_json)
        
        # Compact output
        compact_json = {
            "rs": "I",
            "scn": "B",
            "il": 50,
            "rf": [],
            "cs": "S",
            "rsc": "B",
            "rst": ["playful_tease", "emotional_resonance", "curiosity_hook"]
        }
        compact_str = json.dumps(compact_json)
        
        # Calculate savings
        verbose_len = len(verbose_str)
        compact_len = len(compact_str)
        savings = (verbose_len - compact_len) / verbose_len * 100
        
        print(f"\nScene Analysis Token Savings:")
        print(f"  Verbose: {verbose_len} chars")
        print(f"  Compact: {compact_len} chars")
        print(f"  Savings: {savings:.1f}%")
        
        # Should save at least 30%
        assert savings >= 30
    
    def test_reply_generation_token_savings(self):
        """Test token savings for reply generation."""
        # Verbose output
        verbose_json = {
            "replies": [
                {
                    "text": "Hey! How's your day going?",
                    "strategy": "emotional_resonance",
                    "reasoning": "Start with a warm greeting to establish connection"
                },
                {
                    "text": "I noticed you mentioned travel earlier",
                    "strategy": "curiosity_hook",
                    "reasoning": "Reference previous topic to show attentiveness"
                },
                {
                    "text": "That sounds interesting! Tell me more",
                    "strategy": "playful_tease",
                    "reasoning": "Express enthusiasm to encourage sharing"
                }
            ],
            "overall_advice": "Keep the conversation light and engaging"
        }
        verbose_str = json.dumps(verbose_json)
        
        # Compact output (without reasoning)
        compact_json = {
            "r": [
                ["Hey! How's your day going?", "emotional_resonance"],
                ["I noticed you mentioned travel earlier", "curiosity_hook"],
                ["That sounds interesting! Tell me more", "playful_tease"]
            ],
            "adv": "Keep the conversation light and engaging"
        }
        compact_str = json.dumps(compact_json)
        
        # Calculate savings
        verbose_len = len(verbose_str)
        compact_len = len(compact_str)
        savings = (verbose_len - compact_len) / verbose_len * 100
        
        print(f"\nReply Generation Token Savings:")
        print(f"  Verbose: {verbose_len} chars")
        print(f"  Compact: {compact_len} chars")
        print(f"  Savings: {savings:.1f}%")
        
        # Should save at least 40% (more due to removed reasoning)
        assert savings >= 40


class TestRoundTripIntegration:
    """Test round-trip conversion in integrated flow."""
    
    def test_scene_analysis_round_trip(self):
        """Test that scene analysis survives round-trip conversion."""
        # Original compact JSON
        compact_json = """
        {
            "rs": "I",
            "scn": "B",
            "il": 50,
            "rf": ["test_flag"],
            "cs": "S",
            "rsc": "B",
            "rst": ["playful_tease", "emotional_resonance"]
        }
        """
        
        # Parse and expand
        result = parse_and_expand_scene_analysis(compact_json)
        
        # Verify all fields are correct
        assert result.relationship_state == "ignition"
        assert result.scenario == "BALANCED"
        assert result.intimacy_level == 50
        assert result.risk_flags == ["test_flag"]
        assert result.current_scenario == "SAFE"
        assert result.recommended_scenario == "BALANCED"
        assert len(result.recommended_strategies) == 2
    
    def test_reply_generation_round_trip(self):
        """Test that reply generation survives round-trip conversion."""
        # Original compact JSON
        compact_json = """
        {
            "r": [
                ["Hello!", "emotional_resonance"],
                ["How are you?", "curiosity_hook"]
            ],
            "adv": "Be friendly"
        }
        """
        
        # Parse and expand
        result = parse_and_expand_reply_generation(compact_json)
        
        # Verify structure
        assert len(result["replies"]) == 2
        assert result["replies"][0]["text"] == "Hello!"
        assert result["replies"][0]["strategy"] == "emotional_resonance"
        assert result["replies"][1]["text"] == "How are you?"
        assert result["replies"][1]["strategy"] == "curiosity_hook"
        assert result["overall_advice"] == "Be friendly"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
