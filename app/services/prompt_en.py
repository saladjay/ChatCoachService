from enum import Enum
__all__ = ['PREFERENCE_ANALYSIS_PROMPT', 'SCENARIO_PROMPT', 'SCENARIO_ANALYSIS_PROMPT', 'CONTEXT_SUMMARY_PROMPT', 'CHATCOACH_PROMPT', 'ChatEmotionState', 'TRAIT_DISCOVERY_PROMPT', 'STANDARD_TRAITS', 'TRAIT_MAPPING_PROMPT']

PREFERENCE_ANALYSIS_PROMPT = """
Analyze the conversation and extract the user's communication preferences.

Conversation:
{conversation}

Output JSON only:
{{
  "features": {{
    "formality": <0.0-1.0>,
    "detail_level": <0.0-1.0>,
    "emotional_expression": <0.0-1.0>,
    "humor_preference": <0.0-1.0>,
    "directness": <0.0-1.0>,
    "example_need": <0.0-1.0>,
    "depth_preference": <0.0-1.0>
  }},
  "description": "<one-sentence summary of the user's style>"
}}
"""

SCENARIO_PROMPT = """
You are a social interaction analyst. Identify the user's current strategy type and recommend three suitable strategies.

## Strategy Categories

### Safe / Low Risk
Used in early or cautious stages. Build safety, avoid crossing boundaries.
Codes:
situational_comment, light_humor, neutral_open_question, shared_experience_probe,
empathetic_ack, pace_matching, soft_callback, curiosity_frame,
observational_flirt, appreciation_without_hook, calm_presence, low_pressure_invite

### Balanced / Medium Risk
Used in relationship-building stage. Test attraction with controlled risk.
Codes:
playful_tease, direct_compliment, emotional_resonance, perspective_flip, value_signal,
micro_challenge, assumptive_frame, story_snippet, flirt_with_escape,
selective_vulnerability, energy_injection, forward_reference,
curiosity_hook, consent_check_light

### Risky / High Reward
Used only with strong mutual attraction and high momentum.
Codes:
sexual_hint, dominant_lead, strong_frame_control, bold_assumption,
fast_escalation, taboo_play, polarity_push, emotional_spike,
intimate_projection, scarcity_signal

### Recovery / Repair
Used after conflict or awkward moments.
Codes:
tension_release, boundary_respect, misstep_repair,
emotional_deescalation, graceful_exit

### Negative / Anti-pattern
Should be avoided.
Codes:
validation_seeking, logical_interview, over_explaining,
neediness_signal, performative_niceness

## Conversation
{conversation}

## Output (JSON only)
{{
  "current_scenario": "Safe|Balanced|Risky|Recovery|Negative",
  "recommended_scenario": "Safe|Balanced|Risky|Recovery|Negative",
  "recommended_strategies": ["strategy1","strategy2","strategy3"]
}}
"""


SCENARIO_ANALYSIS_PROMPT = SCENARIO_PROMPT

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

CONTEXT_SUMMARY_PROMPT = """
You are a conversation scenario analyst.

Conversation history:
{conversation}

Classify:
- Emotion: positive | neutral | negative
- Intimacy: stranger | familiar | intimate | recovery
- Scenario: SAFE | BALANCED | RISKY | RECOVERY | NEGATIVE

Output JSON only:
{{
  "conversation_summary": "summary",
  "emotion_state": "positive|neutral|negative",
  "current_intimacy_level": "stranger|familiar|intimate|recovery",
  "scenario": "SAFE|BALANCED|RISKY|RECOVERY|NEGATIVE"
}}
"""

CHATCOACH_PROMPT = """
You are a professional dating conversation coach.

## Scenario
Current: {current_scenario}
Recommended: {recommended_scenario}
Strategies: {recommended_strategies}

## Intimacy
User target: {intimacy_level}
Current: {current_intimacy_level}

## Emotion
{emotion_state}

## Summary
{conversation_summary}

## History
{conversation}

## User Profile
{persona_snapshot_prompt}

## Policy (compiled from traits)
{policy_block}

Constraints:
1. Safety and forbidden rules have highest priority.
2. Follow policy_block for style and structure.
3. Prefer recommended_strategies when compliant.

## User-selected reply
{reply_sentence}

## Language
{language}

## Task
Generate 3 high-quality reply suggestions:
- Match scenario and intimacy
- Prefer recommended strategies
- Match user style
- Advance the conversation naturally
- Avoid excessive enthusiasm or coldness
- Use {language}

## Output (JSON only)
{{
  "replies": [
    {{"text": "...", "strategy": "..."}},
    {{"text": "...", "strategy": "..."}},
    {{"text": "...", "strategy": "..."}}
  ]
}}

All reply texts must be in {language}.
"""

TRAIT_DISCOVERY_PROMPT = """
You are a user profiling assistant.

From the conversation, infer stable traits in:
- expression style
- cognitive style
- decision style
- interaction preference

Rules:
- No predefined labels
- Traits must be abstract concepts
- Each trait includes: trait_name, description, evidence, confidence

Then classify each as:
- general (common)
- personal (highly individual)

Conversation:
{conversation}

Output JSON only:
{{
  "general_traits": [
    {{"trait_name": "...", "description": "...", "evidence": "...", "confidence": 0.0}}
  ],
  "personal_traits": [
    {{"trait_name": "...", "description": "...", "evidence": "...", "confidence": 0.0}}
  ]
}}
"""


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
TRAIT_MAPPING_PROMPT = """
Standard traits:
{standard_traits}

For each input trait:
- MAP to a standard trait with inferred_value
- or NEW with new_trait_name
- or DISCARD if unstable or unimportant

Rules:
- MAP → inferred_value required
- NEW/DISCARD → inferred_value = null

Input traits:
{traits_json}

Output JSON array only:
[
  {{
    "original_trait_name": "...",
    "action": "MAP|NEW|DISCARD",
    "target_trait": "...",
    "new_trait_name": "...",
    "inferred_value": 0.0,
    "confidence": 0.0,
    "reason": "..."
  }}
]
"""
