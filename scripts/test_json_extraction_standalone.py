"""Standalone test for JSON extraction logic (no dependencies)."""


def extract_complete_json_objects(text: str) -> list[str]:
    """Extract all complete JSON objects from text using stack-based bracket matching."""
    results = []
    stack = []
    start_idx = None
    in_string = False
    escape_next = False
    
    for i, char in enumerate(text):
        # Handle string escaping
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        # Track if we're inside a string (to ignore braces in strings)
        if char == '"':
            in_string = not in_string
            continue
        
        # Only process braces outside of strings
        if not in_string:
            if char == '{':
                if not stack:
                    start_idx = i
                stack.append('{')
            elif char == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
                    if not stack and start_idx is not None:
                        # Found a complete JSON object
                        results.append(text[start_idx:i+1])
                        start_idx = None
    
    return results


def test_json_extraction():
    """Test various JSON extraction scenarios."""
    
    test_cases = [
        {
            "name": "Simple JSON",
            "input": '{"key": "value"}',
            "expected_count": 1,
        },
        {
            "name": "JSON with nested objects",
            "input": '{"outer": {"inner": "value"}}',
            "expected_count": 1,
        },
        {
            "name": "JSON with braces in strings",
            "input": '{"message": "This has { and } in it", "data": {"nested": "value"}}',
            "expected_count": 1,
        },
        {
            "name": "Multiple JSON objects",
            "input": '{"first": "obj"} some text {"second": "obj"}',
            "expected_count": 2,
        },
        {
            "name": "JSON in markdown",
            "input": '```json\n{"key": "value"}\n```',
            "expected_count": 1,
        },
        {
            "name": "Incomplete JSON (truncated)",
            "input": '{"key": "value", "incomplete":',
            "expected_count": 0,
        },
        {
            "name": "JSON with escaped quotes",
            "input": '{"message": "He said \\"hello\\"", "data": "test"}',
            "expected_count": 1,
        },
        {
            "name": "Real error case from logs",
            "input": '```json{"screenshot_parse": {"participants": {"self": {"id": "user","nickname": "..."},"other": {"id": "talker","nickname": "ddddddyj"',
            "expected_count": 0,  # Incomplete JSON
        },
    ]
    
    print("Testing JSON extraction logic:\n")
    print("=" * 80)
    
    passed_count = 0
    failed_count = 0
    
    for test in test_cases:
        result = extract_complete_json_objects(test["input"])
        passed = len(result) == test["expected_count"]
        status = "✓ PASS" if passed else "✗ FAIL"
        
        if passed:
            passed_count += 1
        else:
            failed_count += 1
        
        print(f"\n{status} - {test['name']}")
        print(f"  Input: {test['input'][:70]}...")
        print(f"  Expected: {test['expected_count']} objects, Got: {len(result)} objects")
        
        if result:
            for i, obj in enumerate(result):
                print(f"  Object {i+1}: {obj[:80]}...")
    
    print("\n" + "=" * 80)
    print(f"\nResults: {passed_count} passed, {failed_count} failed")
    
    if failed_count == 0:
        print("✓ All tests passed!")
    else:
        print(f"✗ {failed_count} test(s) failed")


if __name__ == "__main__":
    test_json_extraction()
