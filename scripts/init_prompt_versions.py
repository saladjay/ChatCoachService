"""
Initialize Prompt Version Management

This script registers all existing prompts into the version management system.
Run this once to set up the prompt registry.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.prompt_manager import (
    PromptManager,
    PromptType,
    PromptVersion,
)

PROMPTS_DIR = project_root / "prompts"
VERSIONS_DIR = PROMPTS_DIR / "versions"


def _read_version(prompt_type: PromptType, version: PromptVersion) -> str:
    path = VERSIONS_DIR / f"{prompt_type.value}_{version.value}.txt"
    return path.read_text(encoding="utf-8").strip()


def init_prompt_versions():
    """Initialize all prompt versions in the management system"""
    
    print("=" * 80)
    print("INITIALIZING PROMPT VERSION MANAGEMENT")
    print("=" * 80)
    print()
    
    manager = PromptManager()
    
    # ========================================================================
    # V1.0 - Original Versions
    # ========================================================================
    
    print("Registering V1.0 - Original Versions...")
    print("-" * 80)
    
    # Scenario Analysis - Original
    manager.register_prompt(
        prompt_type=PromptType.SCENARIO_ANALYSIS,
        version=PromptVersion.V1_ORIGINAL,
        content=_read_version(PromptType.SCENARIO_ANALYSIS, PromptVersion.V1_ORIGINAL),
        author="initial_dev",
        description="Original scenario analysis prompt with full strategy descriptions",
        tags=["original", "full", "detailed"],
        token_estimate=496,
        performance_notes="Baseline version. Comprehensive but token-heavy."
    )
    print("✓ Registered: scenario_analysis v1.0-original")
    
    # Context Summary - Original
    manager.register_prompt(
        prompt_type=PromptType.CONTEXT_SUMMARY,
        version=PromptVersion.V1_ORIGINAL,
        content=_read_version(PromptType.CONTEXT_SUMMARY, PromptVersion.V1_ORIGINAL),
        author="initial_dev",
        description="Original context summary prompt with full conversation history",
        tags=["original", "full"],
        token_estimate=489,
        performance_notes="Baseline version. Includes full conversation text."
    )
    print("✓ Registered: context_summary v1.0-original")
    
    # Reply Generation - Original
    manager.register_prompt(
        prompt_type=PromptType.REPLY_GENERATION,
        version=PromptVersion.V1_ORIGINAL,
        content=_read_version(PromptType.REPLY_GENERATION, PromptVersion.V1_ORIGINAL),
        author="initial_dev",
        description="Original reply generation prompt with full user profile",
        tags=["original", "full", "detailed"],
        token_estimate=832,
        performance_notes="Baseline version. Most token-heavy component."
    )
    print("✓ Registered: reply_generation v1.0-original")
    
    # Trait Discovery - Original
    manager.register_prompt(
        prompt_type=PromptType.TRAIT_DISCOVERY,
        version=PromptVersion.V1_ORIGINAL,
        content=_read_version(PromptType.TRAIT_DISCOVERY, PromptVersion.V1_ORIGINAL),
        author="initial_dev",
        description="Original trait discovery prompt",
        tags=["original", "user_profile"],
        token_estimate=311,
        performance_notes="Used for learning user traits from conversation."
    )
    print("✓ Registered: trait_discovery v1.0-original")
    
    # Trait Mapping - Original
    manager.register_prompt(
        prompt_type=PromptType.TRAIT_MAPPING,
        version=PromptVersion.V1_ORIGINAL,
        content=_read_version(PromptType.TRAIT_MAPPING, PromptVersion.V1_ORIGINAL),
        author="initial_dev",
        description="Original trait mapping prompt",
        tags=["original", "user_profile"],
        token_estimate=494,
        performance_notes="Maps discovered traits to standard traits."
    )
    print("✓ Registered: trait_mapping v1.0-original")
    
    print()
    
    # ========================================================================
    # V2.0 - Compact Versions
    # ========================================================================
    
    print("Registering V2.0 - Compact Versions...")
    print("-" * 80)
    
    # Scenario Analysis - Compact
    manager.register_prompt(
        prompt_type=PromptType.SCENARIO_ANALYSIS,
        version=PromptVersion.V2_COMPACT,
        content=_read_version(PromptType.SCENARIO_ANALYSIS, PromptVersion.V2_COMPACT),
        author="optimization_team",
        description="Compact scenario analysis prompt with strategy codes only",
        tags=["compact", "optimized", "token-efficient"],
        token_estimate=350,
        performance_notes="29% token reduction. Uses conversation summary instead of full text.",
        parent_version="scenario_analysis_v1.0-original"
    )
    print("✓ Registered: scenario_analysis v2.0-compact (29% reduction)")
    
    # Context Summary - Compact
    manager.register_prompt(
        prompt_type=PromptType.CONTEXT_SUMMARY,
        version=PromptVersion.V2_COMPACT,
        content=_read_version(PromptType.CONTEXT_SUMMARY, PromptVersion.V2_COMPACT),
        author="optimization_team",
        description="Compact context summary prompt with abbreviated conversation",
        tags=["compact", "optimized", "token-efficient"],
        token_estimate=350,
        performance_notes="28% token reduction. Limits to 5 recent messages with truncation.",
        parent_version="context_summary_v1.0-original"
    )
    print("✓ Registered: context_summary v2.0-compact (28% reduction)")
    
    # Reply Generation - Compact
    manager.register_prompt(
        prompt_type=PromptType.REPLY_GENERATION,
        version=PromptVersion.V2_COMPACT,
        content=_read_version(PromptType.REPLY_GENERATION, PromptVersion.V2_COMPACT),
        author="optimization_team",
        description="Compact reply generation prompt with minimal user profile",
        tags=["compact", "optimized", "token-efficient"],
        token_estimate=450,
        performance_notes="46% token reduction. Uses compact user style and last message only.",
        parent_version="reply_generation_v1.0-original"
    )
    print("✓ Registered: reply_generation v2.0-compact (46% reduction)")
    
    print()
    
    # ========================================================================
    # Activate Compact Versions (Default)
    # ========================================================================
    
    print("Activating V2.0 - Compact Versions as default...")
    print("-" * 80)
    
    manager.activate_version(
        PromptType.SCENARIO_ANALYSIS,
        PromptVersion.V2_COMPACT,
        author="system"
    )
    print("✓ Activated: scenario_analysis v2.0-compact")
    
    manager.activate_version(
        PromptType.CONTEXT_SUMMARY,
        PromptVersion.V2_COMPACT,
        author="system"
    )
    print("✓ Activated: context_summary v2.0-compact")
    
    manager.activate_version(
        PromptType.REPLY_GENERATION,
        PromptVersion.V2_COMPACT,
        author="system"
    )
    print("✓ Activated: reply_generation v2.0-compact")
    
    manager.activate_version(
        PromptType.TRAIT_DISCOVERY,
        PromptVersion.V1_ORIGINAL,
        author="system"
    )
    print("✓ Activated: trait_discovery v1.0-original")
    
    manager.activate_version(
        PromptType.TRAIT_MAPPING,
        PromptVersion.V1_ORIGINAL,
        author="system"
    )
    print("✓ Activated: trait_mapping v1.0-original")
    
    print()
    
    # ========================================================================
    # Summary
    # ========================================================================
    
    print("=" * 80)
    print("INITIALIZATION COMPLETE")
    print("=" * 80)
    print()
    
    print("Registered Versions:")
    for prompt_type in PromptType:
        versions = manager.list_versions(prompt_type)
        print(f"\n{prompt_type.value}:")
        for v in versions:
            status = "✓ ACTIVE" if v["is_active"] else "  "
            print(f"  {status} {v['version']} - {v['token_estimate']} tokens")
            print(f"      {v['description']}")
    
    print()
    print("Token Savings Summary:")
    print("-" * 80)
    
    # Calculate savings
    original_total = 496 + 489 + 832  # Scenario + Context + Reply
    compact_total = 350 + 350 + 450
    savings = original_total - compact_total
    savings_pct = (savings / original_total) * 100
    
    print(f"Original Total:  {original_total} tokens")
    print(f"Compact Total:   {compact_total} tokens")
    print(f"Savings:         {savings} tokens ({savings_pct:.1f}%)")
    print()
    
    print("Next Steps:")
    print("1. Use manager.get_active_prompt(PromptType.XXX) to get prompts")
    print("2. Use manager.rollback() to switch versions")
    print("3. Use manager.compare_versions() to analyze differences")
    print("4. Check prompts/ directory for version files")
    print()


if __name__ == "__main__":
    init_prompt_versions()
