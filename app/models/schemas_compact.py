"""Compact schemas for LLM input/output to reduce token usage.

This module defines compact versions of schemas that use abbreviated field names
and compact codes to minimize token consumption in LLM interactions.

Token Savings: 30-45% reduction in output tokens compared to verbose schemas.

Usage:
    1. LLM outputs compact schema
    2. Parse compact schema in code
    3. Expand to full schema using SchemaExpander
    4. Use full schema in application logic
"""

from pydantic import BaseModel, Field


class SceneAnalysisCompact(BaseModel):
    """Compact scene analysis output from LLM.
    
    This schema uses abbreviated field names and compact codes to reduce tokens.
    
    Token Savings Example:
        Verbose: {"relationship_state": "ignition", "scenario": "BALANCED", ...} (~15 tokens)
        Compact: {"rs": "I", "scn": "B", ...} (~8 tokens)
        Savings: ~47% reduction
    
    Field Mappings:
        rs: relationship_state (I|P|V|E)
        scn: scenario (S|B|R|C|N)
        il: intimacy_level (0-101)
        rf: risk_flags (list of strings)
        cs: current_scenario (S|B|R|C|N)
        rsc: recommended_scenario (S|B|R|C|N)
        rst: recommended_strategies (list of strategy codes)
    
    Code Meanings:
        rs: I=ignition, P=propulsion, V=ventilation, E=equilibrium
        scn/cs/rsc: S=SAFE, B=BALANCED, R=RISKY, C=RECOVERY, N=NEGATIVE
    """
    
    rs: str = Field(
        ...,
        description="Relationship state code: I=ignition, P=propulsion, V=ventilation, E=equilibrium",
        pattern="^[IPVE]$"
    )
    
    scn: str = Field(
        ...,
        description="Scenario code: S=SAFE, B=BALANCED, R=RISKY, C=RECOVERY, N=NEGATIVE",
        pattern="^[SBRCN]$"
    )
    
    il: int = Field(
        ...,
        ge=0,
        le=101,
        description="Intimacy level (0-101)"
    )
    
    rf: list[str] = Field(
        default_factory=list,
        description="Risk flags (abbreviated)"
    )
    
    cs: str = Field(
        ...,
        description="Current scenario code: S=SAFE, B=BALANCED, R=RISKY, C=RECOVERY, N=NEGATIVE",
        pattern="^[SBRCN]$"
    )
    
    rsc: str = Field(
        ...,
        description="Recommended scenario code: S=SAFE, B=BALANCED, R=RISKY, C=RECOVERY, N=NEGATIVE",
        pattern="^[SBRCN]$"
    )
    
    rst: list[str] = Field(
        default_factory=list,
        description="Recommended strategies (strategy codes)",
        max_items=5
    )
    
    tone: str | None = Field(
        default=None,
        description="Tone code: P=positive, N=neutral, G=negative, T=tense",
        pattern="^[PNGT]$"
    )


class ReplyGenerationCompact(BaseModel):
    """Compact reply generation output from LLM.
    
    This schema uses a nested list structure to minimize tokens.
    
    Token Savings Example:
        Verbose: {"replies": [{"text": "...", "strategy": "...", "reasoning": "..."}]} (~25 tokens)
        Compact: {"r": [["...", "..."]]} (~10 tokens)
        Savings: ~60% reduction
    
    Field Mappings:
        r: replies (list of [text, strategy] or [text, strategy, reasoning])
        adv: overall_advice (string)
    
    Reply Format:
        Without reasoning: ["text", "strategy"]
        With reasoning: ["text", "strategy", "reasoning"]
    """
    
    r: list[list[str]] = Field(
        ...,
        description="Replies as nested lists: [[text, strategy], ...] or [[text, strategy, reasoning], ...]",
        min_items=1,
        max_items=5
    )
    
    adv: str = Field(
        default="",
        description="Overall advice (optional)",
        max_length=500
    )


class StrategyPlanCompact(BaseModel):
    """Compact strategy plan output from LLM.
    
    This schema is used by the StrategyPlanner service to recommend strategies
    based on scene analysis.
    
    Token Savings Example:
        Verbose: {"recommended": "BALANCED", "weights": {...}, "avoid": [...]} (~20 tokens)
        Compact: {"rec": "B", "w": {...}, "av": [...]} (~12 tokens)
        Savings: ~40% reduction
    
    Field Mappings:
        rec: recommended scenario code (S|B|R|C|N)
        w: strategy weights (dict of strategy -> weight)
        av: strategies to avoid (list of strategy codes)
    """
    
    rec: str = Field(
        ...,
        description="Recommended scenario code: S=SAFE, B=BALANCED, R=RISKY, C=RECOVERY, N=NEGATIVE",
        pattern="^[SBRCN]$"
    )
    
    w: dict[str, float] = Field(
        default_factory=dict,
        description="Strategy weights (strategy_code -> weight 0-1)",
        max_items=10
    )
    
    av: list[str] = Field(
        default_factory=list,
        description="Strategies to avoid (strategy codes)",
        max_items=5
    )


class ContextSummaryCompact(BaseModel):
    """Compact context summary for reduced token usage.
    
    This schema provides a compressed representation of conversation context.
    
    Token Savings Example:
        Verbose: {"conversation_summary": "...", "emotion_state": "positive", ...} (~30 tokens)
        Compact: {"sum": "...", "emo": "P", ...} (~18 tokens)
        Savings: ~40% reduction
    
    Field Mappings:
        sum: conversation summary (brief)
        emo: emotion state code (P|N|G|T)
        il: current intimacy level (0-101)
        rf: risk flags (list)
    """
    
    sum: str = Field(
        ...,
        description="Brief conversation summary",
        max_length=200
    )
    
    emo: str = Field(
        ...,
        description="Emotion state code: P=positive, N=neutral, G=negative, T=tense",
        pattern="^[PNGT]$"
    )
    
    il: int = Field(
        ...,
        ge=0,
        le=101,
        description="Current intimacy level (0-101)"
    )
    
    rf: list[str] = Field(
        default_factory=list,
        description="Risk flags",
        max_items=5
    )


class PersonaSnapshotCompact(BaseModel):
    """Compact persona snapshot for reduced token usage.
    
    Token Savings Example:
        Verbose: {"style": "humorous", "pacing": "normal", ...} (~15 tokens)
        Compact: {"st": "humor", "pc": "N", ...} (~8 tokens)
        Savings: ~47% reduction
    
    Field Mappings:
        st: style (brief description)
        pc: pacing code (S=slow, N=normal, F=fast)
        rt: risk_tolerance code (L=low, M=medium, H=high)
        cf: confidence (0-1)
    """
    
    st: str = Field(
        ...,
        description="Style (brief, e.g., 'humor', 'direct', 'warm')",
        max_length=50
    )
    
    pc: str = Field(
        ...,
        description="Pacing code: S=slow, N=normal, F=fast",
        pattern="^[SNF]$"
    )
    
    rt: str = Field(
        ...,
        description="Risk tolerance code: L=low, M=medium, H=high",
        pattern="^[LMH]$"
    )
    
    cf: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1)"
    )


# Validation helpers

def validate_scenario_code(code: str) -> bool:
    """Validate scenario code.
    
    Args:
        code: Scenario code to validate
    
    Returns:
        True if valid, False otherwise
    
    Examples:
        >>> validate_scenario_code("B")
        True
        >>> validate_scenario_code("X")
        False
    """
    return code.upper() in ["S", "B", "R", "C", "N"]


def validate_relationship_state_code(code: str) -> bool:
    """Validate relationship state code.
    
    Args:
        code: Relationship state code to validate
    
    Returns:
        True if valid, False otherwise
    
    Examples:
        >>> validate_relationship_state_code("I")
        True
        >>> validate_relationship_state_code("X")
        False
    """
    return code.upper() in ["I", "P", "V", "E"]


def validate_tone_code(code: str) -> bool:
    """Validate tone code.
    
    Args:
        code: Tone code to validate
    
    Returns:
        True if valid, False otherwise
    
    Examples:
        >>> validate_tone_code("P")
        True
        >>> validate_tone_code("X")
        False
    """
    return code.upper() in ["P", "N", "G", "T"]
