"""Tests for schema compression functionality.

This module tests the schema compression system including:
- Mapping constants
- Compact schemas
- Schema expansion
- Round-trip conversion
"""

import pytest
from app.services.schema_mappings import (
    get_scenario_code,
    get_scenario_name,
    get_relationship_state_code,
    get_relationship_state_name,
    get_tone_code,
    get_tone_name,
    intimacy_value_to_stage,
    intimacy_value_to_stage_code,
)
from app.models.schemas import SceneAnalysisResult, PersonaSnapshot
from app.models.schemas_compact import (
    SceneAnalysisCompact,
    ReplyGenerationCompact,
    StrategyPlanCompact,
    PersonaSnapshotCompact,
)
from app.services.schema_expander import (
    SchemaExpander,
    SchemaCompressor,
    parse_and_expand_scene_analysis,
    parse_and_expand_reply_generation,
)


class TestSchemaMappings:
    """Test schema mapping functions."""
    
    def test_scenario_code_mapping(self):
        """Test scenario code to name mapping."""
        assert get_scenario_name("S") == "SAFE"
        assert get_scenario_name("B") == "BALANCED"
        assert get_scenario_name("R") == "RISKY"
        assert get_scenario_name("C") == "RECOVERY"
        assert get_scenario_name("N") == "NEGATIVE"
    
    def test_scenario_name_to_code(self):
        """Test scenario name to code mapping."""
        assert get_scenario_code("SAFE") == "S"
        assert get_scenario_code("BALANCED") == "B"
        assert get_scenario_code("RISKY") == "R"
        assert get_scenario_code("RECOVERY") == "C"
        assert get_scenario_code("NEGATIVE") == "N"
    
    def test_scenario_aliases(self):
        """Test scenario alias mapping."""
        assert get_scenario_code("Safe / Low Risk") == "S"
        assert get_scenario_code("Balanced / Medium Risk") == "B"
        assert get_scenario_code("safe/low risk strategy") == "S"
        assert get_scenario_code("balance/medium risk strategy") == "B"
    
    def test_relationship_state_mapping(self):
        """Test relationship state mapping."""
        assert get_relationship_state_name("I") == "ignition"
        assert get_relationship_state_name("P") == "propulsion"
        assert get_relationship_state_name("V") == "ventilation"
        assert get_relationship_state_name("E") == "equilibrium"
    
    def test_relationship_state_reverse(self):
        """Test relationship state reverse mapping."""
        assert get_relationship_state_code("ignition") == "I"
        assert get_relationship_state_code("propulsion") == "P"
        assert get_relationship_state_code("ventilation") == "V"
        assert get_relationship_state_code("equilibrium") == "E"
    
    def test_relationship_state_chinese(self):
        """Test Chinese relationship state aliases."""
        assert get_relationship_state_code("破冰") == "I"
        assert get_relationship_state_code("推进") == "P"
        assert get_relationship_state_code("冷却") == "V"
        assert get_relationship_state_code("维持") == "E"
    
    def test_tone_mapping(self):
        """Test tone mapping."""
        assert get_tone_name("P") == "positive"
        assert get_tone_name("N") == "neutral"
        assert get_tone_name("G") == "negative"
        assert get_tone_name("T") == "tense"
    
    def test_tone_reverse(self):
        """Test tone reverse mapping."""
        assert get_tone_code("positive") == "P"
        assert get_tone_code("neutral") == "N"
        assert get_tone_code("negative") == "G"
        assert get_tone_code("tense") == "T"
    
    def test_intimacy_value_to_stage(self):
        """Test intimacy value to stage conversion."""
        assert intimacy_value_to_stage(10) == "stranger"
        assert intimacy_value_to_stage(30) == "acquaintance"
        assert intimacy_value_to_stage(50) == "friend"
        assert intimacy_value_to_stage(70) == "intimate"
        assert intimacy_value_to_stage(90) == "bonded"
    
    def test_intimacy_value_to_stage_code(self):
        """Test intimacy value to stage code conversion."""
        assert intimacy_value_to_stage_code(10) == "S"
        assert intimacy_value_to_stage_code(30) == "A"
        assert intimacy_value_to_stage_code(50) == "F"
        assert intimacy_value_to_stage_code(70) == "I"
        assert intimacy_value_to_stage_code(90) == "B"


class TestCompactSchemas:
    """Test compact schema validation."""
    
    def test_scene_analysis_compact_valid(self):
        """Test valid scene analysis compact schema."""
        compact = SceneAnalysisCompact(
            rs="I",
            scn="B",
            il=50,
            rf=[],
            cs="S",
            rsc="B",
            rst=["playful_tease", "emotional_resonance"]
        )
        
        assert compact.rs == "I"
        assert compact.scn == "B"
        assert compact.il == 50
        assert len(compact.rst) == 2
    
    def test_scene_analysis_compact_invalid_code(self):
        """Test invalid scenario code raises validation error."""
        with pytest.raises(ValueError):
            SceneAnalysisCompact(
                rs="X",  # Invalid code
                scn="B",
                il=50,
                rf=[],
                cs="S",
                rsc="B",
                rst=[]
            )
    
    def test_reply_generation_compact_valid(self):
        """Test valid reply generation compact schema."""
        compact = ReplyGenerationCompact(
            r=[
                ["Hello!", "emotional_resonance"],
                ["How are you?", "curiosity_hook"]
            ],
            adv="Keep it light and friendly"
        )
        
        assert len(compact.r) == 2
        assert compact.r[0][0] == "Hello!"
        assert compact.adv == "Keep it light and friendly"
    
    def test_strategy_plan_compact_valid(self):
        """Test valid strategy plan compact schema."""
        compact = StrategyPlanCompact(
            rec="B",
            w={"emotional_resonance": 0.9, "playful_tease": 0.7},
            av=["neediness_signal"]
        )
        
        assert compact.rec == "B"
        assert compact.w["emotional_resonance"] == 0.9
        assert "neediness_signal" in compact.av


class TestSchemaExpansion:
    """Test schema expansion functionality."""
    
    def test_expand_scene_analysis(self):
        """Test expanding scene analysis from compact to full."""
        compact = SceneAnalysisCompact(
            rs="I",
            scn="B",
            il=50,
            rf=["Overly high expectations"],
            cs="S",
            rsc="B",
            rst=["playful_tease", "emotional_resonance"]
        )
        
        full = SchemaExpander.expand_scene_analysis(compact)
        
        assert full.relationship_state == "ignition"
        assert full.scenario == "BALANCED"
        assert full.intimacy_level == 50
        assert len(full.risk_flags) == 1
        assert full.current_scenario == "SAFE"
        assert full.recommended_scenario == "BALANCED"
        assert len(full.recommended_strategies) == 2
    
    def test_expand_reply_generation_without_reasoning(self):
        """Test expanding reply generation without reasoning."""
        compact = ReplyGenerationCompact(
            r=[
                ["Hello!", "emotional_resonance"],
                ["How are you?", "curiosity_hook"]
            ],
            adv="Keep it light"
        )
        
        result = SchemaExpander.expand_reply_generation(compact)
        
        assert len(result["replies"]) == 2
        assert result["replies"][0]["text"] == "Hello!"
        assert result["replies"][0]["strategy"] == "emotional_resonance"
        assert result["replies"][0]["reasoning"] == ""
        assert result["overall_advice"] == "Keep it light"
    
    def test_expand_reply_generation_with_reasoning(self):
        """Test expanding reply generation with reasoning."""
        compact = ReplyGenerationCompact(
            r=[
                ["Hello!", "emotional_resonance", "Builds connection"],
                ["How are you?", "curiosity_hook", "Shows interest"]
            ],
            adv="Keep it light"
        )
        
        result = SchemaExpander.expand_reply_generation(compact)
        
        assert len(result["replies"]) == 2
        assert result["replies"][0]["reasoning"] == "Builds connection"
        assert result["replies"][1]["reasoning"] == "Shows interest"
    
    def test_expand_strategy_plan(self):
        """Test expanding strategy plan."""
        compact = StrategyPlanCompact(
            rec="B",
            w={"emotional_resonance": 0.9, "playful_tease": 0.7},
            av=["neediness_signal"]
        )
        
        result = SchemaExpander.expand_strategy_plan(compact)
        
        assert result["recommended_scenario"] == "BALANCED"
        assert result["strategy_weights"]["emotional_resonance"] == 0.9
        assert "neediness_signal" in result["avoid_strategies"]
    
    def test_expand_persona_snapshot(self):
        """Test expanding persona snapshot."""
        compact = PersonaSnapshotCompact(
            st="humor",
            pc="N",
            rt="M",
            cf=0.85
        )
        
        full = SchemaExpander.expand_persona_snapshot(compact)
        
        assert full.style == "humor"
        assert full.pacing == "normal"
        assert full.risk_tolerance == "medium"
        assert full.confidence == 0.85


class TestSchemaCompression:
    """Test schema compression functionality."""
    
    def test_compress_scene_analysis(self):
        """Test compressing scene analysis from full to compact."""
        full = SceneAnalysisResult(
            relationship_state="ignition",
            scenario="BALANCED",
            intimacy_level=50,
            risk_flags=["Overly high expectations"],
            current_scenario="SAFE",
            recommended_scenario="BALANCED",
            recommended_strategies=["playful_tease"]
        )
        
        compact = SchemaCompressor.compress_scene_analysis(full)
        
        assert compact.rs == "I"
        assert compact.scn == "B"
        assert compact.il == 50
        assert len(compact.rf) == 1
        assert compact.cs == "S"
        assert compact.rsc == "B"
    
    def test_compress_persona_snapshot(self):
        """Test compressing persona snapshot."""
        full = PersonaSnapshot(
            style="humorous",
            pacing="normal",
            risk_tolerance="medium",
            confidence=0.85,
            prompt=""
        )
        
        compact = SchemaCompressor.compress_persona_snapshot(full)
        
        assert compact.st == "humorous"
        assert compact.pc == "N"
        assert compact.rt == "M"
        assert compact.cf == 0.85


class TestRoundTripConversion:
    """Test round-trip conversion (full -> compact -> full)."""
    
    def test_scene_analysis_round_trip(self):
        """Test scene analysis round-trip conversion."""
        original = SceneAnalysisResult(
            relationship_state="propulsion",
            scenario="RISKY",
            intimacy_level=75,
            risk_flags=[],
            current_scenario="BALANCED",
            recommended_scenario="RISKY",
            recommended_strategies=["bold_assumption", "intimate_projection"]
        )
        
        # Compress
        compact = SchemaCompressor.compress_scene_analysis(original)
        
        # Expand
        restored = SchemaExpander.expand_scene_analysis(compact)
        
        # Verify
        assert restored.relationship_state == original.relationship_state
        assert restored.scenario == original.scenario
        assert restored.intimacy_level == original.intimacy_level
        assert restored.current_scenario == original.current_scenario
        assert restored.recommended_scenario == original.recommended_scenario
    
    def test_persona_snapshot_round_trip(self):
        """Test persona snapshot round-trip conversion."""
        original = PersonaSnapshot(
            style="direct",
            pacing="fast",
            risk_tolerance="high",
            confidence=0.92,
            prompt="test prompt"
        )
        
        # Compress
        compact = SchemaCompressor.compress_persona_snapshot(original)
        
        # Expand
        restored = SchemaExpander.expand_persona_snapshot(compact, prompt="test prompt")
        
        # Verify
        assert restored.style == original.style
        assert restored.pacing == original.pacing
        assert restored.risk_tolerance == original.risk_tolerance
        assert restored.confidence == original.confidence


class TestJSONParsing:
    """Test JSON parsing and expansion."""
    
    def test_parse_and_expand_scene_analysis(self):
        """Test parsing JSON and expanding scene analysis."""
        json_text = '{"rs":"I","scn":"B","il":50,"rf":[],"cs":"S","rsc":"B","rst":["playful_tease"]}'
        
        result = parse_and_expand_scene_analysis(json_text)
        
        assert result.relationship_state == "ignition"
        assert result.scenario == "BALANCED"
        assert result.intimacy_level == 50
    
    def test_parse_and_expand_reply_generation(self):
        """Test parsing JSON and expanding reply generation."""
        json_text = '{"r":[["Hello!","emotional_resonance"],["How are you?","curiosity_hook"]],"adv":"Keep it light"}'
        
        result = parse_and_expand_reply_generation(json_text)
        
        assert len(result["replies"]) == 2
        assert result["replies"][0]["text"] == "Hello!"
        assert result["overall_advice"] == "Keep it light"
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON raises error."""
        json_text = '{"invalid": json}'
        
        with pytest.raises(ValueError):
            parse_and_expand_scene_analysis(json_text)


class TestTokenSavings:
    """Test token savings calculations."""
    
    def test_scene_analysis_token_savings(self):
        """Test token savings for scene analysis."""
        import json
        
        # Full schema (verbose)
        full_dict = {
            "relationship_state": "ignition",
            "scenario": "BALANCED",
            "intimacy_level": 50,
            "risk_flags": [],
            "current_scenario": "SAFE",
            "recommended_scenario": "BALANCED",
            "recommended_strategies": ["playful_tease", "emotional_resonance"]
        }
        
        # Compact schema
        compact_dict = {
            "rs": "I",
            "scn": "B",
            "il": 50,
            "rf": [],
            "cs": "S",
            "rsc": "B",
            "rst": ["playful_tease", "emotional_resonance"]
        }
        
        full_json = json.dumps(full_dict)
        compact_json = json.dumps(compact_dict)
        
        # Calculate character savings (rough proxy for tokens)
        savings_pct = (len(full_json) - len(compact_json)) / len(full_json) * 100
        
        print(f"\nFull JSON length: {len(full_json)}")
        print(f"Compact JSON length: {len(compact_json)}")
        print(f"Savings: {savings_pct:.1f}%")
        
        # Should save at least 30%
        assert savings_pct >= 30
    
    def test_reply_generation_token_savings(self):
        """Test token savings for reply generation."""
        import json
        
        # Full schema (verbose)
        full_dict = {
            "replies": [
                {"text": "Hello!", "strategy": "emotional_resonance", "reasoning": "Builds connection"},
                {"text": "How are you?", "strategy": "curiosity_hook", "reasoning": "Shows interest"}
            ],
            "overall_advice": "Keep it light and friendly"
        }
        
        # Compact schema
        compact_dict = {
            "r": [
                ["Hello!", "emotional_resonance", "Builds connection"],
                ["How are you?", "curiosity_hook", "Shows interest"]
            ],
            "adv": "Keep it light and friendly"
        }
        
        full_json = json.dumps(full_dict)
        compact_json = json.dumps(compact_dict)
        
        # Calculate character savings
        savings_pct = (len(full_json) - len(compact_json)) / len(full_json) * 100
        
        print(f"\nFull JSON length: {len(full_json)}")
        print(f"Compact JSON length: {len(compact_json)}")
        print(f"Savings: {savings_pct:.1f}%")
        
        # Should save at least 30%
        assert savings_pct >= 30


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
