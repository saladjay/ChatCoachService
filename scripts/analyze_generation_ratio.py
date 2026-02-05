"""Analyze the ratio between generation and merge_step calls in trace data."""

import json
import sys
from collections import defaultdict
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

import analyze_trace


def analyze_generation_ratio(trace_file: str):
    """Analyze why generation calls are more than merge_step calls."""
    
    print("=" * 80)
    print("GENERATION vs MERGE_STEP RATIO ANALYSIS")
    print("=" * 80)
    print()
    
    # Load trace
    entries = analyze_trace.load_trace_file(trace_file)
    llm_calls = analyze_trace.extract_llm_calls(entries)
    
    # Count by task type
    task_counts = defaultdict(int)
    for call in llm_calls:
        task_counts[call['task_type']] += 1
    
    merge_step_count = task_counts.get('merge_step', 0)
    generation_count = task_counts.get('generation', 0)
    
    print(f"Total LLM Calls: {len(llm_calls)}")
    print(f"  - merge_step: {merge_step_count}")
    print(f"  - generation: {generation_count}")
    print(f"  - Ratio (generation/merge_step): {generation_count/merge_step_count:.2f}" if merge_step_count > 0 else "  - Ratio: N/A")
    print()
    
    # Analyze by session
    print("=" * 80)
    print("ANALYSIS BY SESSION")
    print("=" * 80)
    print()
    
    session_stats = defaultdict(lambda: {'merge_step': 0, 'generation': 0, 'other': 0})
    
    for entry in entries:
        if entry.get('type') in ['llm_call_end', 'step_end']:
            session_id = entry.get('conversation_id') or entry.get('session_id')
            if not session_id:
                continue
            
            # Determine task type
            task_type = entry.get('task_type')
            step_name = entry.get('step_name', '')
            
            if not task_type:
                if 'merge_step' in step_name:
                    task_type = 'merge_step'
                elif 'generation' in step_name or 'reply_generation' in step_name:
                    task_type = 'generation'
            
            if task_type == 'merge_step':
                session_stats[session_id]['merge_step'] += 1
            elif task_type == 'generation':
                session_stats[session_id]['generation'] += 1
            else:
                session_stats[session_id]['other'] += 1
    
    # Calculate ratio distribution
    ratio_distribution = defaultdict(int)
    sessions_with_multiple_gen = []
    
    for session_id, stats in session_stats.items():
        merge = stats['merge_step']
        gen = stats['generation']
        
        if merge > 0:
            ratio = gen / merge
            ratio_bucket = round(ratio, 1)
            ratio_distribution[ratio_bucket] += 1
            
            if gen > merge:
                sessions_with_multiple_gen.append((session_id, merge, gen, ratio))
    
    print("Ratio Distribution (generation/merge_step per session):")
    print("-" * 80)
    for ratio in sorted(ratio_distribution.keys()):
        count = ratio_distribution[ratio]
        bar = "█" * min(count, 50)
        print(f"  {ratio:.1f}x: {count:>3} sessions {bar}")
    print()
    
    # Show sessions with multiple generations
    if sessions_with_multiple_gen:
        print("=" * 80)
        print("SESSIONS WITH MULTIPLE GENERATIONS PER MERGE_STEP")
        print("=" * 80)
        print()
        
        sessions_with_multiple_gen.sort(key=lambda x: x[3], reverse=True)
        
        print(f"{'Session ID':<40} {'Merge':<8} {'Gen':<8} {'Ratio':<8}")
        print("-" * 80)
        
        for session_id, merge, gen, ratio in sessions_with_multiple_gen[:20]:
            print(f"{session_id:<40} {merge:<8} {gen:<8} {ratio:.2f}x")
        
        if len(sessions_with_multiple_gen) > 20:
            print(f"\n... and {len(sessions_with_multiple_gen) - 20} more sessions")
        print()
    
    # Analyze step names
    print("=" * 80)
    print("GENERATION STEP NAME BREAKDOWN")
    print("=" * 80)
    print()
    
    generation_step_names = defaultdict(int)
    
    for entry in entries:
        if entry.get('type') == 'step_end':
            step_name = entry.get('step_name', '')
            if 'generation' in step_name or 'reply' in step_name:
                # Check if it has LLM metadata
                has_llm = (
                    entry.get('provider') or 
                    entry.get('model') or 
                    entry.get('input_tokens') or 
                    (isinstance(entry.get('result'), dict) and (
                        entry['result'].get('provider') or 
                        entry['result'].get('model')
                    ))
                )
                if has_llm:
                    generation_step_names[step_name] += 1
    
    print("Step names containing 'generation' or 'reply' with LLM metadata:")
    print("-" * 80)
    for step_name in sorted(generation_step_names.keys(), key=lambda x: generation_step_names[x], reverse=True):
        count = generation_step_names[step_name]
        print(f"  {step_name:<50} {count:>4} calls")
    print()
    
    # Analyze retry patterns
    print("=" * 80)
    print("RETRY PATTERN ANALYSIS")
    print("=" * 80)
    print()
    
    retry_counts = defaultdict(int)
    
    for entry in entries:
        if entry.get('type') == 'step_end':
            step_name = entry.get('step_name', '')
            if 'reply_generation_attempt_' in step_name:
                # Extract attempt number
                try:
                    attempt_num = int(step_name.split('_')[-1])
                    retry_counts[attempt_num] += 1
                except (ValueError, IndexError):
                    pass
    
    if retry_counts:
        print("Reply generation attempts:")
        print("-" * 80)
        for attempt in sorted(retry_counts.keys()):
            count = retry_counts[attempt]
            print(f"  Attempt {attempt}: {count:>4} calls")
        print()
        
        if max(retry_counts.keys()) > 1:
            print("⚠️  Multiple attempts detected - retries are happening!")
            print("   This could be due to:")
            print("   - Intimacy check failures (if enabled)")
            print("   - Timeouts")
            print("   - Other errors")
        else:
            print("✓ No retries detected - all generations succeed on first attempt")
    else:
        print("No retry pattern found in trace data")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    avg_ratio = generation_count / merge_step_count if merge_step_count > 0 else 0
    
    print(f"Overall ratio: {avg_ratio:.2f}x (generation/merge_step)")
    print()
    
    if avg_ratio > 1.5:
        print("⚠️  Generation calls are significantly more than merge_step calls")
        print()
        print("Possible reasons:")
        print("  1. Multiple resources per request (each triggers generation)")
        print("  2. Retry mechanism (intimacy check failures, timeouts)")
        print("  3. prepare_generate_reply calls (in multi-resource scenarios)")
        print("  4. Other generation-related steps being counted")
        print()
        print("Recommendations:")
        print("  - Check the 'SESSIONS WITH MULTIPLE GENERATIONS' section above")
        print("  - Review the 'GENERATION STEP NAME BREAKDOWN' for unexpected steps")
        print("  - Check the 'RETRY PATTERN ANALYSIS' for retry behavior")
    else:
        print("✓ Generation/merge_step ratio is within expected range")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_generation_ratio.py <trace_file>")
        print()
        print("Example:")
        print("  python analyze_generation_ratio.py logs/trace.jsonl")
        sys.exit(1)
    
    trace_file = sys.argv[1]
    
    if not Path(trace_file).exists():
        print(f"Error: Trace file not found: {trace_file}")
        sys.exit(1)
    
    analyze_generation_ratio(trace_file)


if __name__ == "__main__":
    main()
