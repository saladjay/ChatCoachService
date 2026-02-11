"""Check if there's double counting of generation calls in trace analysis."""

import json
import sys
from pathlib import Path
from collections import defaultdict

def check_double_counting(trace_file: str):
    """Check for double counting between llm_call_end and step_end events."""
    
    print("=" * 80)
    print("DOUBLE COUNTING ANALYSIS")
    print("=" * 80)
    print()
    
    with open(trace_file, 'r', encoding='utf-8') as f:
        entries = [json.loads(line.strip()) for line in f if line.strip()]
    
    # Track events by type
    llm_call_ends = []
    step_ends = []
    
    for entry in entries:
        event_type = entry.get('type')
        if event_type == 'llm_call_end':
            llm_call_ends.append(entry)
        elif event_type == 'step_end':
            step_ends.append(entry)
    
    print(f"Total events: {len(entries)}")
    print(f"  - llm_call_end: {len(llm_call_ends)}")
    print(f"  - step_end: {len(step_ends)}")
    print()
    
    # Check step_end events with LLM metadata
    step_ends_with_llm = []
    step_ends_without_llm = []
    
    for entry in step_ends:
        result = entry.get('result', {})
        has_llm = (
            entry.get('provider') or 
            entry.get('model') or 
            entry.get('input_tokens') or 
            entry.get('output_tokens') or 
            (isinstance(result, dict) and (
                result.get('provider') or 
                result.get('model') or
                result.get('input_tokens') or
                result.get('output_tokens')
            ))
        )
        
        if has_llm:
            step_ends_with_llm.append(entry)
        else:
            step_ends_without_llm.append(entry)
    
    print("step_end events breakdown:")
    print(f"  - With LLM metadata: {len(step_ends_with_llm)}")
    print(f"  - Without LLM metadata: {len(step_ends_without_llm)}")
    print()
    
    # Analyze step_end with LLM metadata
    if step_ends_with_llm:
        print("=" * 80)
        print("STEP_END EVENTS WITH LLM METADATA")
        print("=" * 80)
        print()
        
        step_name_counts = defaultdict(int)
        for entry in step_ends_with_llm:
            step_name = entry.get('step_name', 'unknown')
            step_name_counts[step_name] += 1
        
        print(f"{'Step Name':<50} {'Count':<10}")
        print("-" * 80)
        for step_name in sorted(step_name_counts.keys(), key=lambda x: step_name_counts[x], reverse=True):
            count = step_name_counts[step_name]
            print(f"{step_name:<50} {count:<10}")
        print()
    
    # Check for potential double counting
    print("=" * 80)
    print("POTENTIAL DOUBLE COUNTING CHECK")
    print("=" * 80)
    print()
    
    # Group by timestamp (within 100ms window)
    timestamp_groups = defaultdict(list)
    
    for entry in llm_call_ends:
        ts = entry.get('ts', 0)
        timestamp_groups[round(ts, 1)].append(('llm_call_end', entry))
    
    for entry in step_ends_with_llm:
        ts = entry.get('ts', 0)
        timestamp_groups[round(ts, 1)].append(('step_end', entry))
    
    # Find groups with both types
    double_counted = []
    for ts, events in timestamp_groups.items():
        if len(events) > 1:
            types = [e[0] for e in events]
            if 'llm_call_end' in types and 'step_end' in types:
                double_counted.append((ts, events))
    
    if double_counted:
        print(f"⚠️  Found {len(double_counted)} potential double-counted events!")
        print()
        print("Sample of double-counted events:")
        print("-" * 80)
        
        for i, (ts, events) in enumerate(double_counted[:5]):
            print(f"\nTimestamp: {ts}")
            for event_type, entry in events:
                if event_type == 'llm_call_end':
                    print(f"  - llm_call_end: task_type={entry.get('task_type')}, call_id={entry.get('call_id')}")
                else:
                    print(f"  - step_end: step_name={entry.get('step_name')}, step_id={entry.get('step_id')}")
        
        if len(double_counted) > 5:
            print(f"\n... and {len(double_counted) - 5} more")
        print()
    else:
        print("✓ No obvious double counting detected")
        print()
    
    # Calculate expected vs actual
    print("=" * 80)
    print("EXPECTED vs ACTUAL COUNTS")
    print("=" * 80)
    print()
    
    # Expected: llm_call_end only (no step_end with LLM metadata)
    expected_llm_calls = len(llm_call_ends)
    
    # Actual: llm_call_end + step_end with LLM metadata
    actual_llm_calls = len(llm_call_ends) + len(step_ends_with_llm)
    
    print(f"Expected LLM calls (llm_call_end only): {expected_llm_calls}")
    print(f"Actual LLM calls (llm_call_end + step_end with LLM): {actual_llm_calls}")
    print(f"Difference: {actual_llm_calls - expected_llm_calls}")
    print()
    
    if actual_llm_calls > expected_llm_calls:
        print("⚠️  step_end events with LLM metadata are being counted as LLM calls!")
        print()
        print("This causes double counting because:")
        print("  1. llm_call_end records the actual LLM call")
        print("  2. step_end wraps the LLM call and includes the result")
        print("  3. Both are being counted as separate LLM calls")
        print()
        print("Solution:")
        print("  - Only count llm_call_end events")
        print("  - OR only count step_end events (not both)")
        print("  - OR filter out step_end events that wrap llm_call_end")
    else:
        print("✓ No double counting issue")
    print()
    
    # Analyze generation calls specifically
    print("=" * 80)
    print("GENERATION CALLS BREAKDOWN")
    print("=" * 80)
    print()
    
    generation_from_llm_call = 0
    generation_from_step_end = 0
    
    for entry in llm_call_ends:
        if entry.get('task_type') == 'generation':
            generation_from_llm_call += 1
    
    for entry in step_ends_with_llm:
        step_name = entry.get('step_name', '')
        if 'generation' in step_name or 'reply_generation' in step_name:
            generation_from_step_end += 1
    
    print(f"Generation calls from llm_call_end: {generation_from_llm_call}")
    print(f"Generation calls from step_end: {generation_from_step_end}")
    print(f"Total (if both counted): {generation_from_llm_call + generation_from_step_end}")
    print()
    
    if generation_from_step_end > 0:
        print("⚠️  This explains the 1.72:1 ratio!")
        print()
        print("Each generation request creates:")
        print("  1. One llm_call_end event (counted as generation)")
        print("  2. One step_end event with LLM metadata (also counted as generation)")
        print()
        print(f"Expected ratio: 1:1 (99 merge_step : 99 generation)")
        print(f"Actual ratio: ~1.7:1 (99 merge_step : ~170 generation)")
        print()
        print("The extra ~70 generation calls are from step_end events!")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python check_double_counting.py <trace_file>")
        print()
        print("Example:")
        print("  python check_double_counting.py logs/trace.jsonl")
        sys.exit(1)
    
    trace_file = sys.argv[1]
    
    if not Path(trace_file).exists():
        print(f"Error: Trace file not found: {trace_file}")
        sys.exit(1)
    
    check_double_counting(trace_file)


if __name__ == "__main__":
    main()
