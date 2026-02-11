#!/usr/bin/env python3
"""
Test script for merge_step configuration switching.
Tests that USE_MERGE_STEP environment variable correctly switches between flows.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_config_default():
    """Test that default configuration is false (traditional flow)."""
    print("=" * 60)
    print("Test 1: Default Configuration")
    print("=" * 60)
    
    # Import settings (should use default)
    from app.core.config import settings
    
    print(f"\nuse_merge_step: {settings.use_merge_step}")
    print(f"Expected: False (traditional flow)")
    
    assert settings.use_merge_step == False, "Default should be False"
    
    print("\n✓ Default configuration is correct!")
    return True


def test_config_enabled():
    """Test that USE_MERGE_STEP=true enables merge_step flow."""
    print("\n" + "=" * 60)
    print("Test 2: Enable merge_step via Environment Variable")
    print("=" * 60)
    
    # Set environment variable
    os.environ["USE_MERGE_STEP"] = "true"
    
    # Reload settings
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    from app.core.config import settings
    
    print(f"\nUSE_MERGE_STEP env var: {os.environ.get('USE_MERGE_STEP')}")
    print(f"use_merge_step: {settings.use_merge_step}")
    print(f"Expected: True (merge_step flow)")
    
    assert settings.use_merge_step == True, "Should be True when env var is 'true'"
    
    print("\n✓ merge_step enabled correctly!")
    
    # Clean up
    del os.environ["USE_MERGE_STEP"]
    
    return True


def test_config_disabled():
    """Test that USE_MERGE_STEP=false disables merge_step flow."""
    print("\n" + "=" * 60)
    print("Test 3: Disable merge_step via Environment Variable")
    print("=" * 60)
    
    # Set environment variable
    os.environ["USE_MERGE_STEP"] = "false"
    
    # Reload settings
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    from app.core.config import settings
    
    print(f"\nUSE_MERGE_STEP env var: {os.environ.get('USE_MERGE_STEP')}")
    print(f"use_merge_step: {settings.use_merge_step}")
    print(f"Expected: False (traditional flow)")
    
    assert settings.use_merge_step == False, "Should be False when env var is 'false'"
    
    print("\n✓ merge_step disabled correctly!")
    
    # Clean up
    del os.environ["USE_MERGE_STEP"]
    
    return True


def test_function_exists():
    """Test that get_merge_step_analysis_result function exists."""
    print("\n" + "=" * 60)
    print("Test 4: Function Existence Check")
    print("=" * 60)
    
    # Import the module
    import app.api.v1.predict as predict_module
    
    # Check if function exists
    has_function = hasattr(predict_module, 'get_merge_step_analysis_result')
    
    print(f"\nget_merge_step_analysis_result exists: {has_function}")
    
    assert has_function, "get_merge_step_analysis_result function should exist"
    
    # Check function signature
    import inspect
    if has_function:
        func = getattr(predict_module, 'get_merge_step_analysis_result')
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        
        print(f"Function parameters: {params}")
        
        expected_params = ['content_url', 'request', 'orchestrator', 'cache_service']
        assert params == expected_params, f"Parameters mismatch: {params} != {expected_params}"
    
    print("\n✓ Function exists with correct signature!")
    return True


def test_env_example_updated():
    """Test that .env.example has been updated with USE_MERGE_STEP."""
    print("\n" + "=" * 60)
    print("Test 5: .env.example Updated")
    print("=" * 60)
    
    env_example_path = project_root / ".env.example"
    
    if not env_example_path.exists():
        print("\n⚠ .env.example not found, skipping test")
        return True
    
    with open(env_example_path, 'r') as f:
        content = f.read()
    
    has_use_merge_step = "USE_MERGE_STEP" in content
    
    print(f"\nUSE_MERGE_STEP in .env.example: {has_use_merge_step}")
    
    if has_use_merge_step:
        # Extract the line
        for line in content.split('\n'):
            if 'USE_MERGE_STEP' in line and not line.strip().startswith('#'):
                print(f"Configuration line: {line}")
                break
    
    assert has_use_merge_step, "USE_MERGE_STEP should be in .env.example"
    
    print("\n✓ .env.example updated correctly!")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("MERGE STEP CONFIGURATION TEST SUITE")
    print("=" * 80)
    
    try:
        success1 = test_config_default()
        success2 = test_config_enabled()
        success3 = test_config_disabled()
        success4 = test_function_exists()
        success5 = test_env_example_updated()
        
        if all([success1, success2, success3, success4, success5]):
            print("\n" + "=" * 80)
            print("✓ ALL CONFIGURATION TESTS PASSED!")
            print("=" * 80)
            print("\nConfiguration Summary:")
            print("  ✓ Default: USE_MERGE_STEP=false (traditional flow)")
            print("  ✓ Can enable: USE_MERGE_STEP=true (merge_step flow)")
            print("  ✓ Can disable: USE_MERGE_STEP=false (traditional flow)")
            print("  ✓ Function: get_merge_step_analysis_result exists")
            print("  ✓ Documentation: .env.example updated")
            print("\nUsage:")
            print("  # Use traditional flow (default)")
            print("  USE_MERGE_STEP=false python main.py")
            print()
            print("  # Use merge_step optimized flow")
            print("  USE_MERGE_STEP=true python main.py")
            print("=" * 80)
            return True
        else:
            print("\n" + "=" * 80)
            print("✗ SOME TESTS FAILED")
            print("=" * 80)
            return False
            
    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
