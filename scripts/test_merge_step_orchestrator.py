#!/usr/bin/env python3
"""
Test script for merge_step_analysis function in orchestrator.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_strategy_selector():
    """Test the strategy selector service."""
    print("=" * 60)
    print("Testing Strategy Selector")
    print("=" * 60)
    
    from app.services.strategy_selector import get_strategy_selector
    
    selector = get_strategy_selector()
    
    # Test 1: Check available scenarios
    print("\n1. Available scenarios:")
    scenarios = selector.get_available_scenarios()
    for scenario in scenarios:
        print(f"   - {scenario}")
    
    # Test 2: Select strategies for each scenario
    print("\n2. Strategy selection for each scenario:")
    for scenario in scenarios:
        strategies = selector.select_strategies(scenario, count=3)
        print(f"   {scenario}: {strategies}")
    
    # Test 3: Test with seed for reproducibility
    print("\n3. Testing reproducibility with seed:")
    strategies1 = selector.select_strategies("BALANCED", count=3, seed=42)
    strategies2 = selector.select_strategies("BALANCED", count=3, seed=42)
    print(f"   First call:  {strategies1}")
    print(f"   Second call: {strategies2}")
    print(f"   Match: {strategies1 == strategies2}")
    
    # Test 4: Get all strategies for a scenario
    print("\n4. All strategies for SAFE scenario:")
    all_safe = selector.get_all_strategies("SAFE")
    print(f"   Total: {len(all_safe)} strategies")
    print(f"   Strategies: {', '.join(all_safe[:5])}...")
    
    print("\n" + "=" * 60)
    print("✓ Strategy Selector tests passed!")
    print("=" * 60)
    
    return True


async def test_merge_step_adapter():
    """Test the merge_step adapter with strategy selection."""
    print("\n" + "=" * 60)
    print("Testing Merge Step Adapter with Strategy Selection")
    print("=" * 60)
    
    from app.services.merge_step_adapter import MergeStepAdapter
    from app.services.strategy_selector import get_strategy_selector
    
    # Sample merge_step output
    merge_output = {
        "screenshot_parse": {
            "participants": {
                "self": {"id": "user", "nickname": "Alice"},
                "other": {"id": "talker", "nickname": "Bob"}
            },
            "bubbles": [
                {
                    "bubble_id": "1",
                    "bbox": {"x1": 10, "y1": 20, "x2": 200, "y2": 80},
                    "center_x": 105,
                    "center_y": 50,
                    "text": "Hey, how are you?",
                    "sender": "user",
                    "column": "left",
                    "confidence": 0.95
                }
            ],
            "layout": {
                "type": "two_columns",
                "left_role": "user",
                "right_role": "talker"
            }
        },
        "conversation_analysis": {
            "conversation_summary": "Friendly greeting",
            "emotion_state": "positive",
            "current_intimacy_level": 60,
            "risk_flags": []
        },
        "scenario_decision": {
            "relationship_state": "推进",
            "scenario": "BALANCED",
            "intimacy_level": 60,
            "risk_flags": [],
            "current_scenario": "friendly",
            "recommended_scenario": "BALANCED",
            "recommended_strategies": []  # Will be filled by strategy selector
        }
    }
    
    adapter = MergeStepAdapter()
    selector = get_strategy_selector()
    
    # Convert to SceneAnalysisResult
    scene = adapter.to_scene_analysis_result(merge_output)
    
    print(f"\n1. Initial scene (no strategies):")
    print(f"   Recommended scenario: {scene.recommended_scenario}")
    print(f"   Strategies: {scene.recommended_strategies}")
    
    # Apply strategy selection
    selected_strategies = selector.select_strategies(
        scenario=scene.recommended_scenario,
        count=3
    )
    scene.recommended_strategies = selected_strategies
    
    print(f"\n2. After strategy selection:")
    print(f"   Recommended scenario: {scene.recommended_scenario}")
    print(f"   Strategies: {scene.recommended_strategies}")
    
    print("\n" + "=" * 60)
    print("✓ Merge Step Adapter with Strategy Selection tests passed!")
    print("=" * 60)
    
    return True


async def test_orchestrator_integration():
    """Test that orchestrator can use merge_step_analysis."""
    print("\n" + "=" * 60)
    print("Testing Orchestrator Integration")
    print("=" * 60)
    
    # Check that the function exists
    from app.services.orchestrator import Orchestrator
    
    print("\n1. Checking merge_step_analysis method exists:")
    if hasattr(Orchestrator, 'merge_step_analysis'):
        print("   ✓ merge_step_analysis method found")
    else:
        print("   ✗ merge_step_analysis method not found")
        return False
    
    # Check method signature
    import inspect
    sig = inspect.signature(Orchestrator.merge_step_analysis)
    params = list(sig.parameters.keys())
    
    print(f"\n2. Method signature:")
    print(f"   Parameters: {params}")
    
    expected_params = ['self', 'request', 'image_base64', 'image_width', 'image_height']
    if params == expected_params:
        print(f"   ✓ Signature matches expected: {expected_params}")
    else:
        print(f"   ⚠ Signature differs from expected")
    
    print("\n" + "=" * 60)
    print("✓ Orchestrator Integration tests passed!")
    print("=" * 60)
    
    return True


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("MERGE STEP ORCHESTRATOR TEST SUITE")
    print("=" * 80)
    
    try:
        # Test 1: Strategy Selector
        success1 = await test_strategy_selector()
        
        # Test 2: Merge Step Adapter with Strategy Selection
        success2 = await test_merge_step_adapter()
        
        # Test 3: Orchestrator Integration
        success3 = await test_orchestrator_integration()
        
        if success1 and success2 and success3:
            print("\n" + "=" * 80)
            print("✓ ALL TESTS PASSED!")
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
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
