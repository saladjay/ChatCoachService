"""Prompt accessors loaded from prompts/active.

This module centralizes prompt loading to avoid importing legacy prompt files.
"""

from app.services.prompt_manager import get_prompt_manager, PromptType, PromptVersion

prompt_manager = get_prompt_manager()


def _read_active(prompt_type: PromptType) -> str:
    prompt = prompt_manager.get_active_prompt(prompt_type)
    return (prompt or "").strip()


def _read_version(prompt_type: PromptType, version: PromptVersion) -> str:
    prompt = prompt_manager.get_prompt_version(prompt_type, version)
    return (prompt or "").strip()

SCENARIO_PROMPT = _read_active(PromptType.SCENARIO_ANALYSIS)
SCENARIO_ANALYSIS_PROMPT = SCENARIO_PROMPT
CONTEXT_SUMMARY_PROMPT = _read_active(PromptType.CONTEXT_SUMMARY)
CHATCOACH_PROMPT = _read_active(PromptType.REPLY_GENERATION)
TRAIT_DISCOVERY_PROMPT = _read_active(PromptType.TRAIT_DISCOVERY)
TRAIT_MAPPING_PROMPT = _read_active(PromptType.TRAIT_MAPPING)
PREFERENCE_ANALYSIS_PROMPT = _read_active(PromptType.PREFERENCE_ANALYSIS)
CHATCOACH_PROMPT_COMPACT = _read_version(PromptType.REPLY_GENERATION, PromptVersion.V2_COMPACT)
CHATCOACH_PROMPT_COMPACT_V2 = _read_version(PromptType.REPLY_GENERATION, PromptVersion.V3_2_COMPACT_V2_WITHOUT_REASONING)

__all__ = [
    "SCENARIO_PROMPT",
    "SCENARIO_ANALYSIS_PROMPT",
    "CONTEXT_SUMMARY_PROMPT",
    "CHATCOACH_PROMPT",
    "TRAIT_DISCOVERY_PROMPT",
    "TRAIT_MAPPING_PROMPT",
    "PREFERENCE_ANALYSIS_PROMPT",
    "CHATCOACH_PROMPT_COMPACT",
    "CHATCOACH_PROMPT_COMPACT_V2",
]
