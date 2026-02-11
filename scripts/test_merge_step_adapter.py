#!/usr/bin/env python3
"""
Test script for merge_step adapter compatibility with existing data structures.
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.merge_step_adapter import MergeStepAdapter, convert_merge_step_output


def test_adapter():
    """Test that merge_step output can be converted to existing data structures."""
    
    print("=" * 60)
    print("Testing merge_step adapter compatibility")
    print("=" * 60)
    
    # Sample merge_step output (matching the updated prompt format)
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
                },
                {
                    "bubble_id": "2",
                    "bbox": {"x1": 220, "y1": 100, "x2": 410, "y2": 160},
                    "center_x": 315,
                    "center_y": 130,
                    "text": "I'm doing great, thanks!",
                    "sender": "talker",
                    "column": "right",
                    "confidence": 0.98
                }
            ],
            "layout": {
                "type": "two_columns",
                "left_role": "user",
                "right_role": "talker"
            }
        },
        "conversation_analysis": {
            "conversation_summary": "Friendly greeting exchange between Alice and Bob.",
            "emotion_state": "positive",
            "current_intimacy_level": 60,
            "risk_flags": []
        },
        "scenario_decision": {
            "relationship_state": "推进",
            "scenario": "SAFE",
            "intimacy_level": 60,
            "risk_flags": [],
            "current_scenario": "friendly conversation",
            "recommended_scenario": "BALANCED",
            "recommended_strategies": ["BE_SUPPORTIVE", "SHOW_INTEREST", "BE_FRIENDLY"]
        }
    }
    
    adapter = MergeStepAdapter()
    
    # Test 1: Validate merge output
    print("\n1. Validating merge_step output structure...")
    is_valid = adapter.validate_merge_output(merge_output)
    if is_valid:
        print("   ✓ Output structure is valid")
    else:
        print("   ✗ Output structure is invalid")
        return False
    
    # Test 2: Convert to ParsedScreenshotData
    print("\n2. Converting to ParsedScreenshotData...")
    try:
        screenshot_data = adapter.to_parsed_screenshot_data(
            merge_output,
            image_width=500,
            image_height=800
        )
        print(f"   ✓ Conversion successful")
        print(f"      - Image: {screenshot_data.image_meta.width}x{screenshot_data.image_meta.height}")
        print(f"      - Participants: {screenshot_data.participants.self.nickname} & {screenshot_data.participants.other.nickname}")
        print(f"      - Bubbles: {len(screenshot_data.bubbles)}")
        print(f"      - Layout: {screenshot_data.layout.type}")
        
        # Verify bubble structure
        for i, bubble in enumerate(screenshot_data.bubbles):
            print(f"      - Bubble {i+1}: sender={bubble.sender}, text='{bubble.text[:30]}...', confidence={bubble.confidence}")
    except Exception as e:
        print(f"   ✗ Conversion failed: {e}")
        return False
    
    # Test 3: Convert to ContextResult
    print("\n3. Converting to ContextResult...")
    try:
        dialogs = [
            {"speaker": "user", "text": "Hey, how are you?"},
            {"speaker": "talker", "text": "I'm doing great, thanks!"}
        ]
        context_result = adapter.to_context_result(merge_output, dialogs)
        print(f"   ✓ Conversion successful")
        print(f"      - Summary: {context_result.conversation_summary}")
        print(f"      - Emotion: {context_result.emotion_state}")
        print(f"      - Intimacy: {context_result.current_intimacy_level}")
        print(f"      - Risk flags: {context_result.risk_flags}")
        print(f"      - Messages: {len(context_result.conversation)}")
    except Exception as e:
        print(f"   ✗ Conversion failed: {e}")
        return False
    
    # Test 4: Convert to SceneAnalysisResult
    print("\n4. Converting to SceneAnalysisResult...")
    try:
        scene_result = adapter.to_scene_analysis_result(merge_output)
        print(f"   ✓ Conversion successful")
        print(f"      - Relationship state: {scene_result.relationship_state}")
        print(f"      - Scenario: {scene_result.scenario}")
        print(f"      - Recommended scenario: {scene_result.recommended_scenario}")
        print(f"      - Intimacy level: {scene_result.intimacy_level}")
        print(f"      - Strategies: {', '.join(scene_result.recommended_strategies)}")
    except Exception as e:
        print(f"   ✗ Conversion failed: {e}")
        return False
    
    # Test 5: Test convenience function
    print("\n5. Testing convenience function...")
    try:
        screenshot_data, context_result, scene_result = convert_merge_step_output(
            merge_output,
            image_width=500,
            image_height=800,
            dialogs=dialogs
        )
        print(f"   ✓ All conversions successful via convenience function")
    except Exception as e:
        print(f"   ✗ Convenience function failed: {e}")
        return False
    
    # Test 6: Test with invalid output
    print("\n6. Testing validation with invalid output...")
    invalid_output = {"screenshot_parse": {}}  # Missing required fields
    is_valid = adapter.validate_merge_output(invalid_output)
    if not is_valid:
        print("   ✓ Invalid output correctly rejected")
    else:
        print("   ✗ Invalid output incorrectly accepted")
        return False
    
    # Test 7: Verify data type compatibility
    print("\n7. Verifying data type compatibility...")
    try:
        # Check ParsedScreenshotData
        assert hasattr(screenshot_data, 'image_meta')
        assert hasattr(screenshot_data, 'participants')
        assert hasattr(screenshot_data, 'bubbles')
        assert hasattr(screenshot_data, 'layout')
        
        # Check ContextResult
        assert hasattr(context_result, 'conversation_summary')
        assert hasattr(context_result, 'emotion_state')
        assert hasattr(context_result, 'current_intimacy_level')
        assert hasattr(context_result, 'risk_flags')
        assert hasattr(context_result, 'conversation')
        
        # Check SceneAnalysisResult
        assert hasattr(scene_result, 'relationship_state')
        assert hasattr(scene_result, 'scenario')
        assert hasattr(scene_result, 'intimacy_level')
        assert hasattr(scene_result, 'recommended_scenario')
        assert hasattr(scene_result, 'recommended_strategies')
        
        print("   ✓ All data types have required attributes")
    except AssertionError as e:
        print(f"   ✗ Data type compatibility check failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✓ All adapter tests passed!")
    print("✓ merge_step output is compatible with existing data structures")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_adapter()
    sys.exit(0 if success else 1)
