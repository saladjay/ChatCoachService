#!/usr/bin/env python3
"""
Test script for merge_step adapter field filling functionality.
Tests that missing fields are automatically filled with appropriate defaults.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.merge_step_adapter import MergeStepAdapter


def test_missing_center_coordinates():
    """Test that center_x and center_y are calculated from bbox if missing."""
    print("=" * 60)
    print("Test 1: Missing center coordinates")
    print("=" * 60)
    
    merge_output = {
        "screenshot_parse": {
            "participants": {
                "self": {"id": "user", "nickname": "Alice"},
                "other": {"id": "talker", "nickname": "Bob"}
            },
            "bubbles": [
                {
                    # Missing bubble_id, center_x, center_y, column, confidence
                    "bbox": {"x1": 10, "y1": 20, "x2": 200, "y2": 80},
                    "text": "Hello",
                    "sender": "user"
                }
            ],
            "layout": {
                "type": "two_columns"
                # Missing left_role, right_role
            }
        },
        "conversation_analysis": {
            # Missing all fields
        },
        "scenario_decision": {
            # Missing all fields
        }
    }
    
    adapter = MergeStepAdapter()
    screenshot_data = adapter.to_parsed_screenshot_data(merge_output, 500, 800)
    
    bubble = screenshot_data.bubbles[0]
    
    # Check calculated center
    expected_center_x = (10 + 200) / 2  # 105
    expected_center_y = (20 + 80) / 2   # 50
    
    print(f"\nBubble 0:")
    print(f"  bbox: x1={bubble.bbox.x1}, y1={bubble.bbox.y1}, x2={bubble.bbox.x2}, y2={bubble.bbox.y2}")
    print(f"  center_x: {bubble.center_x} (expected: {expected_center_x})")
    print(f"  center_y: {bubble.center_y} (expected: {expected_center_y})")
    print(f"  bubble_id: '{bubble.bubble_id}' (expected: '1')")
    print(f"  column: '{bubble.column}' (expected: 'left' or 'right')")
    print(f"  confidence: {bubble.confidence} (expected: 0.95)")
    
    assert bubble.center_x == expected_center_x, f"center_x mismatch: {bubble.center_x} != {expected_center_x}"
    assert bubble.center_y == expected_center_y, f"center_y mismatch: {bubble.center_y} != {expected_center_y}"
    assert bubble.bubble_id == "1", f"bubble_id mismatch: {bubble.bubble_id} != '1'"
    assert bubble.column in ["left", "right"], f"Invalid column: {bubble.column}"
    assert bubble.confidence == 0.95, f"confidence mismatch: {bubble.confidence} != 0.95"
    
    print("\n✓ All fields correctly filled!")
    return True


def test_missing_layout_roles():
    """Test that layout roles are inferred from bubbles if missing."""
    print("\n" + "=" * 60)
    print("Test 2: Missing layout roles")
    print("=" * 60)
    
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
                    "text": "Hello",
                    "sender": "user",
                    "column": "left",
                    "confidence": 0.95
                },
                {
                    "bubble_id": "2",
                    "bbox": {"x1": 300, "y1": 100, "x2": 490, "y2": 160},
                    "center_x": 395,
                    "center_y": 130,
                    "text": "Hi there",
                    "sender": "talker",
                    "column": "right",
                    "confidence": 0.98
                }
            ],
            "layout": {
                "type": "two_columns"
                # Missing left_role, right_role
            }
        },
        "conversation_analysis": {},
        "scenario_decision": {}
    }
    
    adapter = MergeStepAdapter()
    screenshot_data = adapter.to_parsed_screenshot_data(merge_output, 500, 800)
    
    print(f"\nLayout:")
    print(f"  type: {screenshot_data.layout.type}")
    print(f"  left_role: {screenshot_data.layout.left_role} (expected: 'user')")
    print(f"  right_role: {screenshot_data.layout.right_role} (expected: 'talker')")
    
    assert screenshot_data.layout.left_role == "user", f"left_role mismatch"
    assert screenshot_data.layout.right_role == "talker", f"right_role mismatch"
    
    print("\n✓ Layout roles correctly inferred!")
    return True


def test_missing_conversation_fields():
    """Test that conversation analysis fields have proper defaults."""
    print("\n" + "=" * 60)
    print("Test 3: Missing conversation analysis fields")
    print("=" * 60)
    
    merge_output = {
        "screenshot_parse": {
            "participants": {"self": {"id": "user"}, "other": {"id": "talker"}},
            "bubbles": [],
            "layout": {"type": "two_columns"}
        },
        "conversation_analysis": {
            # All fields missing
        },
        "scenario_decision": {}
    }
    
    adapter = MergeStepAdapter()
    context = adapter.to_context_result(merge_output, [])
    
    print(f"\nContext:")
    print(f"  conversation_summary: '{context.conversation_summary}' (expected: '')")
    print(f"  emotion_state: '{context.emotion_state}' (expected: 'neutral')")
    print(f"  current_intimacy_level: {context.current_intimacy_level} (expected: 50)")
    print(f"  risk_flags: {context.risk_flags} (expected: [])")
    
    assert context.conversation_summary == "", f"conversation_summary should be empty"
    assert context.emotion_state == "neutral", f"emotion_state should be 'neutral'"
    assert context.current_intimacy_level == 50, f"current_intimacy_level should be 50"
    assert context.risk_flags == [], f"risk_flags should be empty list"
    
    print("\n✓ Conversation fields correctly defaulted!")
    return True


def test_missing_scenario_fields():
    """Test that scenario decision fields have proper defaults."""
    print("\n" + "=" * 60)
    print("Test 4: Missing scenario decision fields")
    print("=" * 60)
    
    merge_output = {
        "screenshot_parse": {
            "participants": {"self": {"id": "user"}, "other": {"id": "talker"}},
            "bubbles": [],
            "layout": {"type": "two_columns"}
        },
        "conversation_analysis": {},
        "scenario_decision": {
            # All fields missing
        }
    }
    
    adapter = MergeStepAdapter()
    scene = adapter.to_scene_analysis_result(merge_output)
    
    print(f"\nScene:")
    print(f"  relationship_state: '{scene.relationship_state}' (expected: '维持')")
    print(f"  scenario: '{scene.scenario}' (expected: 'SAFE')")
    print(f"  recommended_scenario: '{scene.recommended_scenario}' (expected: 'SAFE')")
    print(f"  intimacy_level: {scene.intimacy_level} (expected: 50)")
    print(f"  risk_flags: {scene.risk_flags} (expected: [])")
    print(f"  current_scenario: '{scene.current_scenario}' (expected: '')")
    print(f"  recommended_strategies: {scene.recommended_strategies} (expected: [])")
    
    assert scene.relationship_state == "维持", f"relationship_state should be '维持'"
    assert scene.scenario == "SAFE", f"scenario should be 'SAFE'"
    assert scene.recommended_scenario == "SAFE", f"recommended_scenario should be 'SAFE'"
    assert scene.intimacy_level == 50, f"intimacy_level should be 50"
    assert scene.risk_flags == [], f"risk_flags should be empty list"
    assert scene.current_scenario == "", f"current_scenario should be empty"
    assert scene.recommended_strategies == [], f"recommended_strategies should be empty list"
    
    print("\n✓ Scenario fields correctly defaulted!")
    return True


def test_invalid_values_clamping():
    """Test that invalid values are clamped to valid ranges."""
    print("\n" + "=" * 60)
    print("Test 5: Invalid values clamping")
    print("=" * 60)
    
    merge_output = {
        "screenshot_parse": {
            "participants": {"self": {"id": "user"}, "other": {"id": "talker"}},
            "bubbles": [],
            "layout": {"type": "two_columns"}
        },
        "conversation_analysis": {
            "current_intimacy_level": 150,  # Invalid: > 100
            "emotion_state": "invalid_emotion"  # Invalid
        },
        "scenario_decision": {
            "intimacy_level": -10,  # Invalid: < 0
            "relationship_state": "invalid_state",  # Invalid
            "recommended_scenario": "INVALID_SCENARIO"  # Invalid
        }
    }
    
    adapter = MergeStepAdapter()
    context = adapter.to_context_result(merge_output, [])
    scene = adapter.to_scene_analysis_result(merge_output)
    
    print(f"\nContext (after clamping):")
    print(f"  current_intimacy_level: {context.current_intimacy_level} (clamped from 150 to 100)")
    print(f"  emotion_state: '{context.emotion_state}' (defaulted from 'invalid_emotion' to 'neutral')")
    
    print(f"\nScene (after clamping):")
    print(f"  intimacy_level: {scene.intimacy_level} (clamped from -10 to 0)")
    print(f"  relationship_state: '{scene.relationship_state}' (defaulted from 'invalid_state' to '维持')")
    print(f"  recommended_scenario: '{scene.recommended_scenario}' (defaulted from 'INVALID_SCENARIO' to 'SAFE')")
    
    assert context.current_intimacy_level == 100, f"Should clamp to 100"
    assert context.emotion_state == "neutral", f"Should default to 'neutral'"
    assert scene.intimacy_level == 0, f"Should clamp to 0"
    assert scene.relationship_state == "维持", f"Should default to '维持'"
    assert scene.recommended_scenario == "SAFE", f"Should default to 'SAFE'"
    
    print("\n✓ Invalid values correctly clamped!")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("MERGE STEP FIELD FILLING TEST SUITE")
    print("=" * 80)
    
    try:
        success1 = test_missing_center_coordinates()
        success2 = test_missing_layout_roles()
        success3 = test_missing_conversation_fields()
        success4 = test_missing_scenario_fields()
        success5 = test_invalid_values_clamping()
        
        if all([success1, success2, success3, success4, success5]):
            print("\n" + "=" * 80)
            print("✓ ALL FIELD FILLING TESTS PASSED!")
            print("=" * 80)
            print("\nThe adapter can now handle:")
            print("  ✓ Missing center_x, center_y (calculated from bbox)")
            print("  ✓ Missing bubble_id (auto-generated)")
            print("  ✓ Missing column (inferred from position)")
            print("  ✓ Missing confidence (default 0.95)")
            print("  ✓ Missing layout roles (inferred from bubbles)")
            print("  ✓ Missing conversation fields (sensible defaults)")
            print("  ✓ Missing scenario fields (sensible defaults)")
            print("  ✓ Invalid values (clamped to valid ranges)")
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
