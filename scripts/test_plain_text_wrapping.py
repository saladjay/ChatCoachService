#!/usr/bin/env python3
"""Test plain text wrapping fallback for JSON parsing.

This script tests the new fallback mechanism that wraps plain text
responses (like "好的，我明白了。") as JSON objects.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.api.v1.predict import parse_json_with_markdown, _wrap_plain_text_as_json


def test_plain_text_wrapping():
    """Test that plain text is wrapped as JSON."""
    print("=" * 80)
    print("TEST 1: Plain text wrapping")
    print("=" * 80)
    
    test_cases = [
        "好的，我明白了。",
        "Okay, I understand.",
        "Sure thing!",
        "Got it, thanks!",
    ]
    
    for text in test_cases:
        print(f"\nInput: {text}")
        result = parse_json_with_markdown(text)
        print(f"Output: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        # Verify structure
        assert "replies" in result, "Missing 'replies' key"
        assert len(result["replies"]) == 1, "Should have exactly 1 reply"
        assert result["replies"][0]["text"] == text, "Text should match input"
        assert result["replies"][0]["strategy"] == "direct_response", "Strategy should be 'direct_response'"
        print("✓ PASS")
    
    print("\n" + "=" * 80)
    print("All plain text wrapping tests passed!")
    print("=" * 80)


def test_valid_json_not_wrapped():
    """Test that valid JSON is not wrapped."""
    print("\n" + "=" * 80)
    print("TEST 2: Valid JSON should not be wrapped")
    print("=" * 80)
    
    valid_json = '''
    {
        "replies": [
            {"text": "Great!", "strategy": "empathetic_ack", "reasoning": "Positive"},
            {"text": "Tell me more!", "strategy": "open_question", "reasoning": "Interest"},
            {"text": "Awesome!", "strategy": "appreciation", "reasoning": "Support"}
        ]
    }
    '''
    
    print(f"\nInput: {valid_json[:100]}...")
    result = parse_json_with_markdown(valid_json)
    print(f"Output: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    # Verify structure
    assert "replies" in result, "Missing 'replies' key"
    assert len(result["replies"]) == 3, "Should have 3 replies"
    assert result["replies"][0]["text"] == "Great!", "First reply text should match"
    print("✓ PASS")
    
    print("\n" + "=" * 80)
    print("Valid JSON test passed!")
    print("=" * 80)


def test_markdown_wrapped_json():
    """Test that markdown-wrapped JSON is extracted correctly."""
    print("\n" + "=" * 80)
    print("TEST 3: Markdown-wrapped JSON extraction")
    print("=" * 80)
    
    markdown_json = '''```json
    {
        "replies": [
            {"text": "That's wonderful!", "strategy": "empathetic_ack", "reasoning": "Positive"}
        ]
    }
    ```'''
    
    print(f"\nInput: {markdown_json[:100]}...")
    result = parse_json_with_markdown(markdown_json)
    print(f"Output: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    # Verify structure
    assert "replies" in result, "Missing 'replies' key"
    assert len(result["replies"]) == 1, "Should have 1 reply"
    assert result["replies"][0]["text"] == "That's wonderful!", "Reply text should match"
    print("✓ PASS")
    
    print("\n" + "=" * 80)
    print("Markdown-wrapped JSON test passed!")
    print("=" * 80)


def test_long_text_not_wrapped():
    """Test that long text (>500 chars) is not wrapped."""
    print("\n" + "=" * 80)
    print("TEST 4: Long text should not be wrapped")
    print("=" * 80)
    
    long_text = "A" * 600  # 600 characters
    
    print(f"\nInput: {long_text[:100]}... (length: {len(long_text)})")
    
    try:
        result = parse_json_with_markdown(long_text)
        print("✗ FAIL: Should have raised JSONDecodeError")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✓ PASS: Correctly raised JSONDecodeError: {str(e)[:100]}...")
    
    print("\n" + "=" * 80)
    print("Long text test passed!")
    print("=" * 80)


def test_wrap_plain_text_function():
    """Test the _wrap_plain_text_as_json function directly."""
    print("\n" + "=" * 80)
    print("TEST 5: Direct _wrap_plain_text_as_json function test")
    print("=" * 80)
    
    text = "好的，我明白了。"
    print(f"\nInput: {text}")
    
    result = _wrap_plain_text_as_json(text)
    print(f"Output: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    # Verify structure
    assert "replies" in result, "Missing 'replies' key"
    assert len(result["replies"]) == 1, "Should have exactly 1 reply"
    assert result["replies"][0]["text"] == text, "Text should match input"
    assert result["replies"][0]["strategy"] == "direct_response", "Strategy should be 'direct_response'"
    assert result["replies"][0]["reasoning"] == "LLM returned plain text, wrapped automatically", "Reasoning should indicate wrapping"
    print("✓ PASS")
    
    print("\n" + "=" * 80)
    print("Direct function test passed!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_plain_text_wrapping()
        test_valid_json_not_wrapped()
        test_markdown_wrapped_json()
        test_long_text_not_wrapped()
        test_wrap_plain_text_function()
        
        print("\n" + "=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
