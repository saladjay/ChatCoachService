#!/usr/bin/env python3
"""
Test script for merge_step prompt integration with prompt management system.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.prompt_manager import get_prompt_manager, PromptType, PromptVersion


def test_merge_step_prompt():
    """Test that merge_step prompt is properly registered and accessible."""
    
    print("=" * 60)
    print("Testing merge_step prompt integration")
    print("=" * 60)
    
    pm = get_prompt_manager()
    
    # Test 1: Check if MERGE_STEP is in PromptType enum
    print("\n1. Checking PromptType enum...")
    try:
        merge_step_type = PromptType.MERGE_STEP
        print(f"   ✓ PromptType.MERGE_STEP exists: {merge_step_type.value}")
    except AttributeError as e:
        print(f"   ✗ PromptType.MERGE_STEP not found: {e}")
        return False
    
    # Test 2: Check if prompt version file exists
    print("\n2. Checking prompt version file...")
    version_file = project_root / "prompts" / "versions" / "merge_step_v1.0-original.txt"
    if version_file.exists():
        print(f"   ✓ Version file exists: {version_file}")
        with open(version_file, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"   ✓ Content length: {len(content)} characters")
    else:
        print(f"   ✗ Version file not found: {version_file}")
        return False
    
    # Test 3: Check if metadata file exists
    print("\n3. Checking metadata file...")
    metadata_file = project_root / "prompts" / "metadata" / "merge_step_v1.0-original.json"
    if metadata_file.exists():
        print(f"   ✓ Metadata file exists: {metadata_file}")
        metadata = pm.get_metadata("merge_step_v1.0-original")
        if metadata:
            print(f"   ✓ Metadata loaded successfully")
            print(f"      - Type: {metadata.prompt_type}")
            print(f"      - Version: {metadata.version}")
            print(f"      - Description: {metadata.description}")
            print(f"      - Token estimate: {metadata.token_estimate}")
            print(f"      - Tags: {', '.join(metadata.tags)}")
        else:
            print(f"   ✗ Failed to load metadata")
            return False
    else:
        print(f"   ✗ Metadata file not found: {metadata_file}")
        return False
    
    # Test 4: Check registry
    print("\n4. Checking registry...")
    versions = pm.list_versions(PromptType.MERGE_STEP)
    if versions:
        print(f"   ✓ Found {len(versions)} version(s) in registry:")
        for v in versions:
            print(f"      - {v['version']} (created: {v['created_at']})")
    else:
        print(f"   ✗ No versions found in registry")
        return False
    
    # Test 5: Try to get prompt content
    print("\n5. Testing prompt retrieval...")
    try:
        content = pm.get_prompt_version(PromptType.MERGE_STEP, PromptVersion.V1_ORIGINAL)
        if content:
            print(f"   ✓ Successfully retrieved prompt content")
            print(f"   ✓ Content preview (first 200 chars):")
            print(f"      {content[:200]}...")
        else:
            print(f"   ✗ Failed to retrieve prompt content")
            return False
    except Exception as e:
        print(f"   ✗ Error retrieving prompt: {e}")
        return False
    
    # Test 6: Test activation (optional - don't actually activate)
    print("\n6. Testing activation capability...")
    print(f"   ℹ Skipping actual activation to preserve current active prompts")
    print(f"   ℹ To activate, run: pm.activate_version(PromptType.MERGE_STEP, PromptVersion.V1_ORIGINAL)")
    
    print("\n" + "=" * 60)
    print("✓ All tests passed! merge_step prompt is properly integrated.")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_merge_step_prompt()
    sys.exit(0 if success else 1)
