"""Mapping constants for schema compression.

This module provides bidirectional mappings between compact codes and full values
to reduce token usage in LLM inputs/outputs while maintaining readability in code.

Token Savings: Using single-letter codes instead of full words reduces output tokens by 30-45%.

Example:
    Verbose: "relationship_state": "ignition" (5 tokens)
    Compact: "rs": "I" (2 tokens)
    Savings: 60% reduction
"""

# Scenario mappings (场景映射)
# Maps compact codes to full scenario names
SCENARIO_MAP = {
    "S": "SAFE",           # 安全/低风险策略
    "B": "BALANCED",       # 平衡/中风险策略
    "R": "RISKY",          # 高风险/高回报策略
    "C": "RECOVERY",       # 关系修复策略
    "N": "NEGATIVE"        # 禁止的策略
}

# Reverse mapping: full name -> compact code
SCENARIO_REVERSE_MAP = {v: k for k, v in SCENARIO_MAP.items()}

# Alternative full names (for compatibility)
SCENARIO_ALIASES = {
    "Safe / Low Risk": "S",
    "Balanced / Medium Risk": "B",
    "Risky / High Reward": "R",
    "Recovery / Repair": "C",
    "Negative / Anti-pattern": "N",
    "safe/low risk strategy": "S",
    "balance/medium risk strategy": "B",
    "risky/high reward strategy": "R",
    "recovery/repair strategy": "C",
    "negative/anti-pattern strategy": "N",
}


# Relationship state mappings (关系状态映射)
# Maps compact codes to full relationship states
RELATIONSHIP_STATE_MAP = {
    "I": "ignition",       # 破冰 - 初期阶段，需要建立连接
    "P": "propulsion",     # 推进 - 关系发展阶段
    "V": "ventilation",    # 冷却 - 需要降温或调整
    "E": "equilibrium"     # 维持 - 稳定状态
}

# Reverse mapping: full name -> compact code
RELATIONSHIP_STATE_REVERSE_MAP = {v: k for k, v in RELATIONSHIP_STATE_MAP.items()}

# Chinese aliases (for compatibility)
RELATIONSHIP_STATE_ALIASES = {
    "破冰": "I",
    "推进": "P",
    "冷却": "V",
    "维持": "E",
}


# Tone/Emotion mappings (情绪/语气映射)
# Maps compact codes to full tone descriptions
TONE_MAP = {
    "P": "positive",       # 积极的
    "N": "neutral",        # 中性的
    "G": "negative",       # 消极的
    "T": "tense"          # 紧张的
}

# Reverse mapping: full name -> compact code
TONE_REVERSE_MAP = {v: k for k, v in TONE_MAP.items()}


# Intimacy stage mappings (亲密度阶段映射)
# Maps compact codes to full intimacy stages
INTIMACY_STAGE_MAP = {
    "S": "stranger",       # 陌生人 (0-20)
    "A": "acquaintance",   # 熟人 (21-40)
    "F": "friend",         # 朋友 (41-60)
    "I": "intimate",       # 亲密 (61-80)
    "B": "bonded"          # 深度连接 (81-100)
}

# Reverse mapping: full name -> compact code
INTIMACY_STAGE_REVERSE_MAP = {v: k for k, v in INTIMACY_STAGE_MAP.items()}


# Risk level mappings (风险等级映射)
# Maps compact codes to full risk levels
RISK_LEVEL_MAP = {
    "L": "low",            # 低风险
    "M": "medium",         # 中风险
    "H": "high"            # 高风险
}

# Reverse mapping: full name -> compact code
RISK_LEVEL_REVERSE_MAP = {v: k for k, v in RISK_LEVEL_MAP.items()}


# Quality tier mappings (质量等级映射)
# Maps compact codes to full quality tiers
QUALITY_MAP = {
    "C": "cheap",          # 便宜/快速
    "N": "normal",         # 正常
    "P": "premium"         # 高级
}

# Reverse mapping: full name -> compact code
QUALITY_REVERSE_MAP = {v: k for k, v in QUALITY_MAP.items()}


def get_scenario_code(scenario: str) -> str:
    """Get compact code for scenario.
    
    Args:
        scenario: Full scenario name (e.g., "BALANCED", "Balance / Medium Risk")
    
    Returns:
        Compact code (e.g., "B")
    
    Examples:
        >>> get_scenario_code("BALANCED")
        'B'
        >>> get_scenario_code("Balance / Medium Risk")
        'B'
        >>> get_scenario_code("safe/low risk strategy")
        'S'
    """
    # Try direct reverse lookup
    if scenario in SCENARIO_REVERSE_MAP:
        return SCENARIO_REVERSE_MAP[scenario]
    
    # Try aliases
    if scenario in SCENARIO_ALIASES:
        return SCENARIO_ALIASES[scenario]
    
    # Try case-insensitive match
    scenario_lower = scenario.lower()
    for alias, code in SCENARIO_ALIASES.items():
        if alias.lower() == scenario_lower:
            return code
    
    # Default to BALANCED if unknown
    return "B"


def get_scenario_name(code: str) -> str:
    """Get full scenario name from compact code.
    
    Args:
        code: Compact code (e.g., "B")
    
    Returns:
        Full scenario name (e.g., "BALANCED")
    
    Examples:
        >>> get_scenario_name("B")
        'BALANCED'
        >>> get_scenario_name("S")
        'SAFE'
    """
    return SCENARIO_MAP.get(code.upper(), "BALANCED")


def get_relationship_state_code(state: str) -> str:
    """Get compact code for relationship state.
    
    Args:
        state: Full state name (e.g., "ignition", "破冰")
    
    Returns:
        Compact code (e.g., "I")
    
    Examples:
        >>> get_relationship_state_code("ignition")
        'I'
        >>> get_relationship_state_code("破冰")
        'I'
    """
    # Try direct reverse lookup
    if state in RELATIONSHIP_STATE_REVERSE_MAP:
        return RELATIONSHIP_STATE_REVERSE_MAP[state]
    
    # Try Chinese aliases
    if state in RELATIONSHIP_STATE_ALIASES:
        return RELATIONSHIP_STATE_ALIASES[state]
    
    # Default to equilibrium if unknown
    return "E"


def get_relationship_state_name(code: str) -> str:
    """Get full relationship state name from compact code.
    
    Args:
        code: Compact code (e.g., "I")
    
    Returns:
        Full state name (e.g., "ignition")
    
    Examples:
        >>> get_relationship_state_name("I")
        'ignition'
        >>> get_relationship_state_name("P")
        'propulsion'
    """
    return RELATIONSHIP_STATE_MAP.get(code.upper(), "equilibrium")


def get_tone_code(tone: str) -> str:
    """Get compact code for tone.
    
    Args:
        tone: Full tone name (e.g., "positive")
    
    Returns:
        Compact code (e.g., "P")
    
    Examples:
        >>> get_tone_code("positive")
        'P'
        >>> get_tone_code("negative")
        'G'
    """
    return TONE_REVERSE_MAP.get(tone.lower(), "N")


def get_tone_name(code: str) -> str:
    """Get full tone name from compact code.
    
    Args:
        code: Compact code (e.g., "P")
    
    Returns:
        Full tone name (e.g., "positive")
    
    Examples:
        >>> get_tone_name("P")
        'positive'
        >>> get_tone_name("G")
        'negative'
    """
    return TONE_MAP.get(code.upper(), "neutral")


def get_intimacy_stage_code(stage: str) -> str:
    """Get compact code for intimacy stage.
    
    Args:
        stage: Full stage name (e.g., "stranger")
    
    Returns:
        Compact code (e.g., "S")
    
    Examples:
        >>> get_intimacy_stage_code("stranger")
        'S'
        >>> get_intimacy_stage_code("intimate")
        'I'
    """
    return INTIMACY_STAGE_REVERSE_MAP.get(stage.lower(), "A")


def get_intimacy_stage_name(code: str) -> str:
    """Get full intimacy stage name from compact code.
    
    Args:
        code: Compact code (e.g., "S")
    
    Returns:
        Full stage name (e.g., "stranger")
    
    Examples:
        >>> get_intimacy_stage_name("S")
        'stranger'
        >>> get_intimacy_stage_name("I")
        'intimate'
    """
    return INTIMACY_STAGE_MAP.get(code.upper(), "acquaintance")


def intimacy_value_to_stage(intimacy: int) -> str:
    """Convert intimacy value (0-101) to stage name.
    
    Args:
        intimacy: Intimacy value (0-101)
    
    Returns:
        Stage name (e.g., "stranger", "friend")
    
    Examples:
        >>> intimacy_value_to_stage(15)
        'stranger'
        >>> intimacy_value_to_stage(50)
        'friend'
        >>> intimacy_value_to_stage(85)
        'bonded'
    """
    if intimacy <= 20:
        return "stranger"
    elif intimacy <= 40:
        return "acquaintance"
    elif intimacy <= 60:
        return "friend"
    elif intimacy <= 80:
        return "intimate"
    else:
        return "bonded"


def intimacy_value_to_stage_code(intimacy: int) -> str:
    """Convert intimacy value (0-101) to compact stage code.
    
    Args:
        intimacy: Intimacy value (0-101)
    
    Returns:
        Compact stage code (e.g., "S", "F", "B")
    
    Examples:
        >>> intimacy_value_to_stage_code(15)
        'S'
        >>> intimacy_value_to_stage_code(50)
        'F'
        >>> intimacy_value_to_stage_code(85)
        'B'
    """
    stage = intimacy_value_to_stage(intimacy)
    return get_intimacy_stage_code(stage)
