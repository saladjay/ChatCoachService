"""
Prompt utilities for version tracking and management.

This module provides utilities for:
- Adding version identifiers to prompts
- Extracting version identifiers from prompts
- Removing version identifiers before sending to LLM
"""

import re
from typing import Tuple
from enum import Enum

from user_profile.intimacy import intimacy_label_en, intimacy_label_zh
from user_profile import get_age_segment_label, get_age_segment_code


# Regex pattern to match prompt version identifier at the start of a prompt
# Format: [PROMPT:identifier] or [PROMPT:identifier:version]
# Examples: [PROMPT:scene_v1], [PROMPT:generation_compact_v2]
PROMPT_VERSION_PATTERN = re.compile(r'^\[PROMPT:([^\]]+)\]\s*', re.MULTILINE)


def extract_prompt_version(prompt: str) -> Tuple[str | None, str]:
    """Extract prompt version identifier from prompt text.
    
    The version identifier should be at the very beginning of the prompt
    in the format: [PROMPT:identifier]
    
    Args:
        prompt: The prompt text that may contain a version identifier
    
    Returns:
        Tuple of (version_identifier, prompt_without_version)
        - version_identifier: The extracted identifier (e.g., "scene_v1") or None if not found
        - prompt_without_version: The prompt text with version identifier removed
    
    Examples:
        >>> extract_prompt_version("[PROMPT:scene_v1]\\nAnalyze this...")
        ("scene_v1", "Analyze this...")
        
        >>> extract_prompt_version("No version here")
        (None, "No version here")
    """
    match = PROMPT_VERSION_PATTERN.match(prompt)
    
    if match:
        version_id = match.group(1)
        # Remove the version identifier from the prompt
        clean_prompt = PROMPT_VERSION_PATTERN.sub('', prompt, count=1).lstrip()
        return version_id, clean_prompt
    
    return None, prompt


def add_prompt_version(prompt: str, version_id: str) -> str:
    """Add a version identifier to the beginning of a prompt.
    
    Args:
        prompt: The prompt text
        version_id: The version identifier (e.g., "scene_v1", "generation_compact_v2")
    
    Returns:
        Prompt with version identifier prepended
    
    Examples:
        >>> add_prompt_version("Analyze this...", "scene_v1")
        "[PROMPT:scene_v1]\\nAnalyze this..."
    """
    # Check if prompt already has a version identifier
    existing_version, _ = extract_prompt_version(prompt)
    if existing_version:
        # Already has a version, don't add another
        return prompt
    
    return f"[PROMPT:{version_id}]\n{prompt}"


def validate_version_id(version_id: str) -> bool:
    """Validate that a version identifier follows the expected format.
    
    Valid formats:
    - alphanumeric with underscores: scene_v1, generation_compact_v2
    - can include colons for sub-versions: scene:compact:v1
    
    Args:
        version_id: The version identifier to validate
    
    Returns:
        True if valid, False otherwise
    
    Examples:
        >>> validate_version_id("scene_v1")
        True
        >>> validate_version_id("generation:compact:v2")
        True
        >>> validate_version_id("invalid version!")
        False
    """
    # Allow alphanumeric, underscores, colons, and hyphens
    pattern = re.compile(r'^[a-zA-Z0-9_:.-]+$')
    return bool(pattern.match(version_id))


class ChatEmotionState(Enum):
    # 积极正向
    HAPPY_JOYFUL = "happy_joyful"  # 开心愉悦
    EXCITED_ANTICIPATING = "excited_anticipating"  # 兴奋期待
    RELAXED_COMFORTABLE = "relaxed_comfortable"  # 放松舒适
    FLIRTATIOUS_PLAYFUL = "flirtatious_playful"  # 暧昧调情
    
    # 中性平稳
    POLITE_FORMAL = "polite_formal"  # 礼貌客气
    CALM_NEUTRAL = "calm_neutral"  # 平静中立
    CURIOUS_EXPLORING = "curious_exploring"  # 好奇探索
    
    # 消极负面
    COLD_DISTANT = "cold_distant"  # 冷淡疏离
    ANXIOUS_NERVOUS = "anxious_nervous"  # 焦虑不安
    DISAPPOINTED_SAD = "disappointed_sad"  # 失望沮丧
    ANGRY_UPSET = "angry_upset"  # 生气不满
    DEFENSIVE_GUARDED = "defensive_guarded"  # 防御戒备

STANDARD_TRAITS = [
    "depth_preference",
    "abstraction_level",
    "learning_speed",
    "reflection_tendency",
    "logic_vs_intuition",
    "structure_need",
    "example_need",
    "brevity_preference",
    "directness_level",
    "emotional_expression",
    "initiative_level",
    "feedback_sensitivity",
    "control_preference",
    "engagement_stability",
    "intimacy_comfort",
    "risk_tolerance",
    "decision_speed",
    "certainty_need",
    "exploration_tendency",
    "consistency_preference",
    "openness",
    "agreeableness",
    "dominance",
    "patience",
    "self_disclosure",
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_user_style_compact(profile_dict: dict, language: str = "en", drop_behavioral=True) -> str:
    """
    Format user profile in compact form.
    
    Reduces from ~800 chars to ~200 chars (75% reduction)
    
    Args:
        profile_dict: User profile dictionary
    
    Returns:
        Compact string representation
    """
    parts = []
    
    # Explicit tags (compact)
    if 'explicit' in profile_dict:
        explicit = profile_dict['explicit']
        if explicit.get('role'):
            parts.append(f"Role: {', '.join(explicit['role'])}")
        if explicit.get('response_style'):
            parts.append(f"Style: {', '.join(explicit['response_style'])}")
        if explicit.get('forbidden'):
            parts.append(f"Avoid: {', '.join(explicit['forbidden'])}")
        if 'intimacy' in explicit:
            try:
                intimacy_value = int(float(explicit['intimacy']))
                label = (
                    intimacy_label_zh(intimacy_value)
                    if str(language or "").lower().startswith("zh")
                    else intimacy_label_en(intimacy_value)
                )
                parts.append(f"Intimacy: {label} ({intimacy_value}/100)")
            except Exception:
                parts.append(f"Intimacy: {explicit['intimacy']}")
        if 'age' in explicit:
            age_code = get_age_segment_code(explicit['age'])
            if age_code:
                parts.append(f"Age: {age_code}")
        if 'gender' in explicit:
            gender = explicit['gender']
            if gender:
                parts.append(f"Gender: {gender}")
    
    # Top traits only (compact)
    if 'behavioral' in profile_dict and not drop_behavioral:
        behavioral = profile_dict['behavioral']
        top_traits = []
        for trait_name, trait_data in list(behavioral.items())[:3]:  # Top 3 only
            if isinstance(trait_data, dict) and 'value' in trait_data:
                value = trait_data['value']
                top_traits.append(f"{trait_name}({value:.2f})")
        if top_traits:
            parts.append(f"Traits: {', '.join(top_traits)}")
    
    # Policy (compact)
    if 'policy_block' in profile_dict:
        policy = profile_dict['policy_block']
        # Extract first line only
        first_line = policy.split('\n')[0] if policy else ""
        if first_line:
            parts.append(f"Policy: {first_line[:999]}")
    
    return "\n".join(parts)


def format_conversation_compact(messages: list, max_messages: int = 5) -> str:
    """
    Format conversation in compact form.
    
    Reduces from ~1,500 chars to ~500 chars (67% reduction)
    
    Args:
        messages: List of message objects
        max_messages: Maximum number of recent messages to include
    
    Returns:
        Compact conversation string
    """
    if not messages:
        return "No history"
    
    # Take only recent messages
    recent = messages[-max_messages:] if len(messages) > max_messages else messages
    
    lines = []
    for msg in recent:
        speaker = msg.speaker if hasattr(msg, 'speaker') else msg.get('speaker', 'U')
        content = msg.content if hasattr(msg, 'content') else msg.get('content', '')
        
        # Abbreviate speaker
        speaker_abbr = 'U' if speaker == 'user' or speaker == 'me' else 'T'
        
        # Truncate long messages
        content_short = content[:999] + '...' if len(content) > 999 else content
        
        lines.append(f"{speaker_abbr}: {content_short}")
    
    return "\n".join(lines)


def get_last_message(messages: list) -> str:
    """
    Get the last message from conversation.
    
    Args:
        messages: List of message objects
    
    Returns:
        Last message content
    """
    if not messages:
        return ""
    
    last = messages[-1]
    content = last.content if hasattr(last, 'content') else last.get('content', '')
    return content[:999]  # Limit to 999 chars
