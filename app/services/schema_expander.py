"""Utilities for expanding compact schemas to full schemas.

This module provides functions to convert compact LLM outputs (with abbreviated
field names and codes) back to full application schemas.

Usage Flow:
    1. LLM outputs compact schema (e.g., SceneAnalysisCompact)
    2. Parse compact schema from JSON
    3. Expand to full schema (e.g., SceneAnalysisResult)
    4. Use full schema in application logic

Token Savings: 30-45% reduction in LLM output tokens while maintaining
full functionality in application code.
"""

from app.models.schemas import (
    SceneAnalysisResult,
    PersonaSnapshot,
    ContextResult,
)
from app.models.schemas_compact import (
    SceneAnalysisCompact,
    ReplyGenerationCompact,
    StrategyPlanCompact,
    ContextSummaryCompact,
    PersonaSnapshotCompact,
)
from app.services.schema_mappings import (
    get_scenario_name,
    get_relationship_state_name,
    get_tone_name,
    SCENARIO_MAP,
    RELATIONSHIP_STATE_MAP,
    TONE_MAP,
)


class SchemaExpander:
    """Expand compact schemas to full schemas.
    
    This class provides static methods to convert compact LLM outputs
    back to full application schemas.
    """
    
    @staticmethod
    def expand_scene_analysis(compact: SceneAnalysisCompact) -> SceneAnalysisResult:
        """Expand compact scene analysis to full schema.
        
        Converts abbreviated field names and codes to full values.
        
        Args:
            compact: Compact scene analysis from LLM
        
        Returns:
            Full SceneAnalysisResult with expanded values
        
        Examples:
            >>> compact = SceneAnalysisCompact(
            ...     rs="I", scn="B", il=50, rf=[], cs="S", rsc="B", rst=["playful_tease"]
            ... )
            >>> result = SchemaExpander.expand_scene_analysis(compact)
            >>> result.relationship_state
            'ignition'
            >>> result.scenario
            'BALANCED'
        """
        return SceneAnalysisResult(
            relationship_state=get_relationship_state_name(compact.rs),
            scenario=get_scenario_name(compact.rsc),  # Use recommended scenario
            intimacy_level=compact.il,
            risk_flags=compact.rf,
            current_scenario=get_scenario_name(compact.cs),
            recommended_scenario=get_scenario_name(compact.rsc),
            recommended_strategies=compact.rst
        )
    
    @staticmethod
    def expand_reply_generation(compact: ReplyGenerationCompact) -> dict:
        """Expand compact reply generation to full format.
        
        Converts nested list format to structured dictionary format.
        
        Args:
            compact: Compact reply from LLM
        
        Returns:
            Dictionary with 'replies' list and 'overall_advice' string
        
        Examples:
            >>> compact = ReplyGenerationCompact(
            ...     r=[["Hello!", "emotional_resonance"], ["How are you?", "curiosity_hook"]],
            ...     adv="Keep it light and friendly"
            ... )
            >>> result = SchemaExpander.expand_reply_generation(compact)
            >>> len(result['replies'])
            2
            >>> result['replies'][0]['text']
            'Hello!'
        """
        replies = []
        
        for item in compact.r:
            if len(item) == 2:
                # Format: [text, strategy]
                replies.append({
                    "text": item[0],
                    "strategy": item[1],
                    "reasoning": ""  # No reasoning in compact mode
                })
            elif len(item) == 3:
                # Format: [text, strategy, reasoning]
                replies.append({
                    "text": item[0],
                    "strategy": item[1],
                    "reasoning": item[2]
                })
            elif len(item) == 1:
                # Format: [text] - no strategy specified
                replies.append({
                    "text": item[0],
                    "strategy": "",
                    "reasoning": ""
                })
        
        return {
            "replies": replies,
            "overall_advice": compact.adv
        }
    
    @staticmethod
    def expand_strategy_plan(compact: StrategyPlanCompact) -> dict:
        """Expand compact strategy plan to full format.
        
        Args:
            compact: Compact strategy plan from LLM
        
        Returns:
            Dictionary with expanded strategy plan
        
        Examples:
            >>> compact = StrategyPlanCompact(
            ...     rec="B",
            ...     w={"emotional_resonance": 0.9, "playful_tease": 0.7},
            ...     av=["neediness_signal"]
            ... )
            >>> result = SchemaExpander.expand_strategy_plan(compact)
            >>> result['recommended_scenario']
            'BALANCED'
        """
        return {
            "recommended_scenario": get_scenario_name(compact.rec),
            "strategy_weights": compact.w,
            "avoid_strategies": compact.av
        }
    
    @staticmethod
    def expand_context_summary(compact: ContextSummaryCompact) -> dict:
        """Expand compact context summary to full format.
        
        Args:
            compact: Compact context summary
        
        Returns:
            Dictionary with expanded context
        
        Examples:
            >>> compact = ContextSummaryCompact(
            ...     sum="Discussing travel and books",
            ...     emo="P",
            ...     il=50,
            ...     rf=[]
            ... )
            >>> result = SchemaExpander.expand_context_summary(compact)
            >>> result['emotion_state']
            'positive'
        """
        return {
            "conversation_summary": compact.sum,
            "emotion_state": get_tone_name(compact.emo),
            "current_intimacy_level": compact.il,
            "risk_flags": compact.rf
        }
    
    @staticmethod
    def expand_persona_snapshot(compact: PersonaSnapshotCompact, prompt: str = "") -> PersonaSnapshot:
        """Expand compact persona snapshot to full schema.
        
        Args:
            compact: Compact persona snapshot
            prompt: Optional prompt text to include
        
        Returns:
            Full PersonaSnapshot
        
        Examples:
            >>> compact = PersonaSnapshotCompact(
            ...     st="humor",
            ...     pc="N",
            ...     rt="M",
            ...     cf=0.85
            ... )
            >>> result = SchemaExpander.expand_persona_snapshot(compact)
            >>> result.style
            'humor'
            >>> result.pacing
            'normal'
        """
        # Map pacing codes
        pacing_map = {"S": "slow", "N": "normal", "F": "fast"}
        pacing = pacing_map.get(compact.pc.upper(), "normal")
        
        # Map risk tolerance codes
        risk_map = {"L": "low", "M": "medium", "H": "high"}
        risk_tolerance = risk_map.get(compact.rt.upper(), "medium")
        
        return PersonaSnapshot(
            style=compact.st,
            pacing=pacing,
            risk_tolerance=risk_tolerance,
            confidence=compact.cf,
            prompt=prompt
        )


class SchemaCompressor:
    """Compress full schemas to compact schemas.
    
    This class provides static methods to convert full application schemas
    to compact formats for LLM prompts (when needed).
    """
    
    @staticmethod
    def compress_scene_analysis(full: SceneAnalysisResult) -> SceneAnalysisCompact:
        """Compress full scene analysis to compact schema.
        
        This is useful when you need to pass scene analysis back to LLM
        in a compact format.
        
        Args:
            full: Full SceneAnalysisResult
        
        Returns:
            Compact SceneAnalysisCompact
        
        Examples:
            >>> full = SceneAnalysisResult(
            ...     relationship_state="ignition",
            ...     scenario="BALANCED",
            ...     intimacy_level=50,
            ...     risk_flags=[],
            ...     current_scenario="SAFE",
            ...     recommended_scenario="BALANCED",
            ...     recommended_strategies=["playful_tease"]
            ... )
            >>> compact = SchemaCompressor.compress_scene_analysis(full)
            >>> compact.rs
            'I'
            >>> compact.scn
            'B'
        """
        from app.services.schema_mappings import (
            get_relationship_state_code,
            get_scenario_code,
        )
        
        return SceneAnalysisCompact(
            rs=get_relationship_state_code(full.relationship_state),
            scn=get_scenario_code(full.scenario),
            il=full.intimacy_level,
            rf=full.risk_flags,
            cs=get_scenario_code(full.current_scenario),
            rsc=get_scenario_code(full.recommended_scenario),
            rst=full.recommended_strategies
        )
    
    @staticmethod
    def compress_persona_snapshot(full: PersonaSnapshot) -> PersonaSnapshotCompact:
        """Compress full persona snapshot to compact schema.
        
        Args:
            full: Full PersonaSnapshot
        
        Returns:
            Compact PersonaSnapshotCompact
        
        Examples:
            >>> full = PersonaSnapshot(
            ...     style="humorous",
            ...     pacing="normal",
            ...     risk_tolerance="medium",
            ...     confidence=0.85,
            ...     prompt=""
            ... )
            >>> compact = SchemaCompressor.compress_persona_snapshot(full)
            >>> compact.pc
            'N'
            >>> compact.rt
            'M'
        """
        # Map pacing to codes
        pacing_reverse_map = {"slow": "S", "normal": "N", "fast": "F"}
        pc = pacing_reverse_map.get(full.pacing.lower(), "N")
        
        # Map risk tolerance to codes
        risk_reverse_map = {"low": "L", "medium": "M", "high": "H"}
        rt = risk_reverse_map.get(full.risk_tolerance.lower(), "M")
        
        return PersonaSnapshotCompact(
            st=full.style,
            pc=pc,
            rt=rt,
            cf=full.confidence
        )


# Convenience functions for common operations

def parse_and_expand_scene_analysis(json_text: str) -> SceneAnalysisResult:
    """Parse JSON text and expand to full scene analysis.
    
    Args:
        json_text: JSON string from LLM output
    
    Returns:
        Full SceneAnalysisResult
    
    Raises:
        ValueError: If JSON is invalid or doesn't match schema
    
    Examples:
        >>> json_text = '{"rs":"I","scn":"B","il":50,"rf":[],"cs":"S","rsc":"B","rst":[]}'
        >>> result = parse_and_expand_scene_analysis(json_text)
        >>> result.relationship_state
        'ignition'
    """
    import json
    
    try:
        text = json_text.strip()
        
        # 处理 markdown 代码块
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()
        
        # 提取 JSON 对象
        if "{" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]
        
        data = json.loads(text)
        compact = SceneAnalysisCompact(**data)
        return SchemaExpander.expand_scene_analysis(compact)
    except Exception as e:
        raise ValueError(f"Failed to parse and expand scene analysis: {e}") from e


def parse_and_expand_reply_generation(json_text: str) -> dict:
    """Parse JSON text and expand to full reply generation.
    
    Args:
        json_text: JSON string from LLM output
    
    Returns:
        Dictionary with expanded replies
    
    Raises:
        ValueError: If JSON is invalid or doesn't match schema
    
    Examples:
        >>> json_text = '{"r":[["Hello!","emotional_resonance"]],"adv":"Keep it light"}'
        >>> result = parse_and_expand_reply_generation(json_text)
        >>> result['replies'][0]['text']
        'Hello!'
    """
    import json
    
    try:
        text = json_text.strip()
        
        # 处理 markdown 代码块
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()
        
        # 提取 JSON 对象
        if "{" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]
        
        data = json.loads(text)
        compact = ReplyGenerationCompact(**data)
        return SchemaExpander.expand_reply_generation(compact)
    except Exception as e:
        raise ValueError(f"Failed to parse and expand reply generation: {e}") from e
