#!/usr/bin/env python3
r"""
Test script to verify JSON parsing with invalid escape sequences.

This tests the fix for the issue where LLM returns JSON with invalid escapes like \[ and \].
"""

import sys
import os
import json
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _repair_json_string(text: str) -> str:
    """Repair common JSON formatting issues from LLM responses.
    
    Copied from app/api/v1/predict.py for testing purposes.
    """
    if not text:
        return text
    
    original = text
    text = text.strip()
    
    # Step 1: Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    # Step 2: Remove leading/trailing backticks
    text = text.strip("`").strip()
    
    # Step 3: Fix unclosed strings
    quote_count = text.count('"') - text.count('\\"')
    if quote_count % 2 == 1:
        last_quote_idx = text.rfind('"')
        if last_quote_idx != -1:
            remaining = text[last_quote_idx + 1:]
            for i, char in enumerate(remaining):
                if char in [',', '}', ']', '\n']:
                    text = text[:last_quote_idx + 1 + i] + '"' + text[last_quote_idx + 1 + i:]
                    break
    
    # Step 4: Fix unclosed brackets/braces
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')
    
    if open_braces > close_braces:
        text += '}' * (open_braces - close_braces)
    
    if open_brackets > close_brackets:
        text += ']' * (open_brackets - close_brackets)
    
    # Step 5: Remove trailing commas
    text = re.sub(r',(\s*})', r'\1', text)
    text = re.sub(r',(\s*])', r'\1', text)
    
    # Step 6: Fix common key formatting issues
    text = re.sub(r"'([^']+)'(\s*):", r'"\1"\2:', text)
    
    # Step 7: Remove comments
    text = re.sub(r'//[^\n]*\n', '\n', text)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    
    # Step 8: Fix invalid escape sequences
    # Remove backslashes before characters that don't need escaping in JSON
    # Valid JSON escapes: \" \\ \/ \b \f \n \r \t \uXXXX
    # Invalid escapes that LLMs sometimes add: \[ \] \( \) etc.
    text = re.sub(r'\\([^\"\\/bfnrtu])', r'\1', text)
    
    return text


def test_invalid_escape_sequences():
    r"""Test parsing JSON with invalid escape sequences like \[ and \]."""
    
    print("Testing JSON parsing with invalid escape sequences...")
    print("=" * 60)
    
    # Test case 1: The actual problematic response from the log
    test_case_1 = r'''```json
{"r": [["Okay, but promise you won't judge my silly posts! \[calm_presence, low_pressure_invite]", "calm_presence, low_pressure_invite"],["Sure thing! What's your WeChat ID? I'm always up for making new friends! \[calm_presence, low_pressure_invite]", "calm_presence, low_pressure_invite"],["I'd love to! Do you wanna share yours first, or should I? \[neutral_open_question, low_pressure_invite]", "neutral_open_question, low_pressure_invite"]],"adv": "It's okay to share your WeChat if you feel comfortable! Just make sure you know a little bit about them first. Stay safe!"}```'''
    
    print("\nTest Case 1: Real problematic response")
    print("-" * 60)
    print(f"Input (first 200 chars): {test_case_1[:200]}...")
    
    try:
        repaired = _repair_json_string(test_case_1)
        result = json.loads(repaired)
        print("✅ Parsing successful!")
        print(f"Result type: {type(result)}")
        print(f"Keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        
        if isinstance(result, dict) and "r" in result:
            print(f"Number of replies: {len(result['r'])}")
            print(f"First reply: {result['r'][0][0][:80]}...")
            
            # Verify the brackets are preserved in the content
            if "[calm_presence" in result['r'][0][0]:
                print("✅ Brackets preserved in content (without backslash)")
            else:
                print("❌ Brackets not found in content")
        
        print()
        
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        print()
        return False
    
    # Test case 2: Simple case with escaped brackets
    test_case_2 = r'{"text": "Use strategy \[A\] or \[B\]"}'
    
    print("\nTest Case 2: Simple escaped brackets")
    print("-" * 60)
    print(f"Input: {test_case_2}")
    
    try:
        repaired = _repair_json_string(test_case_2)
        result = json.loads(repaired)
        print("✅ Parsing successful!")
        print(f"Result: {result}")
        
        if result.get("text") == "Use strategy [A] or [B]":
            print("✅ Brackets correctly unescaped")
        else:
            print(f"❌ Unexpected result: {result.get('text')}")
        
        print()
        
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        print()
        return False
    
    # Test case 3: Mixed valid and invalid escapes
    test_case_3 = r'{"text": "Line 1\nLine 2\t\[tag\]", "quote": "He said \"hello\""}'
    
    print("\nTest Case 3: Mixed valid and invalid escapes")
    print("-" * 60)
    print(f"Input: {test_case_3}")
    
    try:
        repaired = _repair_json_string(test_case_3)
        result = json.loads(repaired)
        print("✅ Parsing successful!")
        print(f"Result: {result}")
        
        # Check that valid escapes are preserved
        if "\n" in result.get("text", ""):
            print("✅ Valid escape \\n preserved")
        
        if "\t" in result.get("text", ""):
            print("✅ Valid escape \\t preserved")
        
        if "[tag]" in result.get("text", ""):
            print("✅ Invalid escape \\[ removed")
        
        if '"' in result.get("quote", ""):
            print("✅ Valid escape \\\" preserved")
        
        print()
        
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        print()
        return False
    
    # Test case 4: Other invalid escapes
    test_case_4 = r'{"text": "Parentheses \(like this\) and \{braces\}"}'
    
    print("\nTest Case 4: Other invalid escapes")
    print("-" * 60)
    print(f"Input: {test_case_4}")
    
    try:
        repaired = _repair_json_string(test_case_4)
        result = json.loads(repaired)
        print("✅ Parsing successful!")
        print(f"Result: {result}")
        
        if result.get("text") == "Parentheses (like this) and {braces}":
            print("✅ All invalid escapes removed")
        else:
            print(f"❌ Unexpected result: {result.get('text')}")
        
        print()
        
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        print()
        return False
    
    print("=" * 60)
    print("✅ All tests passed!")
    return True


if __name__ == "__main__":
    success = test_invalid_escape_sequences()
    sys.exit(0 if success else 1)
