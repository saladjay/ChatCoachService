"""Extract failed JSON replies from trace.jsonl and attempt to fix them."""

import json
import sys
from pathlib import Path
from datetime import datetime


def extract_complete_json_objects(text: str) -> list[str]:
    """Extract all complete JSON objects using stack-based bracket matching."""
    results = []
    stack = []
    start_idx = None
    in_string = False
    escape_next = False
    
    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"':
            in_string = not in_string
            continue
        
        if not in_string:
            if char == '{':
                if not stack:
                    start_idx = i
                stack.append('{')
            elif char == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
                    if not stack and start_idx is not None:
                        results.append(text[start_idx:i+1])
                        start_idx = None
    
    return results


def try_parse_json(text: str) -> tuple[bool, dict | None, str]:
    """Try to parse JSON with multiple strategies.
    
    Returns:
        (success, parsed_json, error_message)
    """
    original_text = text
    text = text.strip()
    
    # Strategy 1: Direct JSON parsing
    try:
        return True, json.loads(text), ""
    except json.JSONDecodeError as e:
        pass
    
    # Strategy 2: Markdown JSON code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            extracted = text[start:end].strip()
            try:
                return True, json.loads(extracted), ""
            except json.JSONDecodeError:
                pass
    
    # Strategy 3: Simple code blocks
    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            extracted = text[start:end].strip()
            try:
                return True, json.loads(extracted), ""
            except json.JSONDecodeError:
                pass
    
    # Strategy 4: Simple regex extraction
    if "{" in text:
        start = text.find("{")
        end = text.rfind("}") + 1
        if end > start:
            extracted = text[start:end]
            try:
                return True, json.loads(extracted), ""
            except json.JSONDecodeError:
                pass
    
    # Strategy 5: Stack-based extraction
    json_objects = extract_complete_json_objects(text)
    for json_str in json_objects:
        try:
            return True, json.loads(json_str), ""
        except json.JSONDecodeError:
            continue
    
    return False, None, f"Could not extract valid JSON from: {original_text[:100]}..."


def analyze_failed_json(failed_json_file: str, trace_file: str = None):
    """Analyze a failed JSON reply and try to find it in trace."""
    
    print("=" * 80)
    print("FAILED JSON ANALYSIS")
    print("=" * 80)
    print()
    
    # Load failed JSON record
    with open(failed_json_file, 'r', encoding='utf-8') as f:
        failed_record = json.load(f)
    
    print(f"Failed JSON File: {failed_json_file}")
    print(f"Session ID: {failed_record.get('session_id')}")
    print(f"Timestamp: {failed_record.get('timestamp')}")
    print(f"Error: {failed_record.get('error')}")
    print(f"Source: {failed_record.get('source')}")
    print()
    
    # Get raw text
    raw_text = failed_record.get('raw_text') or failed_record.get('reply_text', '')
    print(f"Raw Text Length: {len(raw_text)} characters")
    print(f"Raw Text Preview: {raw_text[:200]}")
    print()
    
    # Try to parse
    print("=" * 80)
    print("ATTEMPTING TO PARSE")
    print("=" * 80)
    print()
    
    success, parsed, error = try_parse_json(raw_text)
    
    if success:
        print("✓ Successfully parsed JSON!")
        print()
        print("Parsed JSON:")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
        print()
    else:
        print("✗ Failed to parse JSON")
        print(f"Error: {error}")
        print()
        
        # Analyze the text
        print("=" * 80)
        print("TEXT ANALYSIS")
        print("=" * 80)
        print()
        
        print(f"Text type: {type(raw_text)}")
        print(f"Text length: {len(raw_text)}")
        print(f"Contains '{{': {'{' in raw_text}")
        print(f"Contains '}}': {'}' in raw_text}")
        print(f"Contains '```': {'```' in raw_text}")
        print()
        
        # Check if it's plain text (not JSON)
        if not '{' in raw_text:
            print("⚠️  This appears to be PLAIN TEXT, not JSON!")
            print()
            print("Possible reasons:")
            print("  1. LLM did not understand the JSON format requirement")
            print("  2. Prompt is not clear enough about JSON output")
            print("  3. Model is not good at generating JSON")
            print("  4. Context or conversation confused the LLM")
            print()
            print("Recommendations:")
            print("  - Check the prompt template")
            print("  - Add explicit JSON format examples")
            print("  - Use a model better at JSON generation")
            print("  - Consider using OpenAI's JSON mode or function calling")
        else:
            print("Text contains JSON-like characters, but parsing failed")
            print()
            print("Possible reasons:")
            print("  1. JSON is incomplete (truncated)")
            print("  2. JSON has syntax errors")
            print("  3. JSON is malformed")
            print()
            
            # Try to identify the issue
            if raw_text.count('{') != raw_text.count('}'):
                print(f"⚠️  Unbalanced braces: {{ count={raw_text.count('{')} }} count={raw_text.count('}')}")
            
            if raw_text.count('[') != raw_text.count(']'):
                print(f"⚠️  Unbalanced brackets: [ count={raw_text.count('[')} ] count={raw_text.count(']')}")
    
    # Search in trace if provided
    if trace_file and Path(trace_file).exists():
        print()
        print("=" * 80)
        print("SEARCHING IN TRACE")
        print("=" * 80)
        print()
        
        session_id = failed_record.get('session_id')
        if session_id:
            print(f"Searching for session: {session_id}")
            
            with open(trace_file, 'r', encoding='utf-8') as f:
                matching_lines = []
                for line in f:
                    if session_id in line:
                        matching_lines.append(line)
            
            print(f"Found {len(matching_lines)} matching lines in trace")
            print()
            
            # Look for LLM responses
            llm_responses = []
            for line in matching_lines:
                try:
                    entry = json.loads(line.strip())
                    if entry.get('type') == 'llm_call_end' and entry.get('task_type') == 'generation':
                        llm_responses.append(entry)
                except:
                    continue
            
            if llm_responses:
                print(f"Found {len(llm_responses)} LLM generation responses:")
                print()
                
                for i, response in enumerate(llm_responses, 1):
                    print(f"Response {i}:")
                    print(f"  Provider: {response.get('provider')}")
                    print(f"  Model: {response.get('model')}")
                    print(f"  Input tokens: {response.get('input_tokens')}")
                    print(f"  Output tokens: {response.get('output_tokens')}")
                    
                    text = response.get('text', '')
                    print(f"  Text length: {len(text)}")
                    print(f"  Text preview: {text[:200]}")
                    print()
                    
                    # Try to parse this response
                    success, parsed, error = try_parse_json(text)
                    if success:
                        print("  ✓ This response can be parsed!")
                        print(f"  Parsed: {json.dumps(parsed, indent=4, ensure_ascii=False)[:200]}...")
                    else:
                        print(f"  ✗ This response also fails to parse: {error}")
                    print()
            else:
                print("No LLM generation responses found in trace")
                print()
                print("This might mean:")
                print("  - The request failed before reaching generation")
                print("  - The trace is incomplete")
                print("  - The session ID doesn't match")
        else:
            print("No session ID found in failed record")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python extract_failed_json_from_trace.py <failed_json_file> [trace_file]")
        print()
        print("Example:")
        print("  python extract_failed_json_from_trace.py logs/failed_json_replies/failed_reply_xxx.json logs/trace.jsonl")
        sys.exit(1)
    
    failed_json_file = sys.argv[1]
    trace_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(failed_json_file).exists():
        print(f"Error: Failed JSON file not found: {failed_json_file}")
        sys.exit(1)
    
    analyze_failed_json(failed_json_file, trace_file)


if __name__ == "__main__":
    main()
