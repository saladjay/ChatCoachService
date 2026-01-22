"""
Prompt utilities for version tracking and management.

This module provides utilities for:
- Adding version identifiers to prompts
- Extracting version identifiers from prompts
- Removing version identifiers before sending to LLM
"""

import re
from typing import Tuple


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
