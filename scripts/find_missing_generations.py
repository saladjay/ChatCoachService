"""Find sessions that have merge_step but no generation."""

import json
import sys
from pathlib import Path
from collections import defaultdict


def find_missing_generations(trace_file: str):
    """Find sessions with merge_step but no generation."""
    
    print("=" * 80)
    print("MISSING GENERATION ANALYSIS")
    print("=" * 80)
    print()
    
    with open(trace_file, 'r', encoding='utf-8') as f:
        entries = [json.loads(line.strip()) for line in f if line.strip()]
    
    # Track sessions
    sessions = defaultdict(lambda: {
        'merge_step': [],
        'generation': [],
        'errors': [],
        'all_events': []
    })
    
    for entry in entries:
        session_id = entry.get('conversation_id') or entry.get('session_id')
        if not session_id:
            continue
        
        sessions[session_id]['all_events'].append(entry)
        
        event_type = entry.get('type')
        
        # Track merge_step
        if event_type == 'step_end':
            step_name = entry.get('step_name', '')
            if 'merge_step' in step_name:
                # Check if it has top-level LLM metadata
                if entry.get('provider') or entry.get('model'):
                    sessions[session_id]['merge_step'].append(entry)
        
        # Track generation
        if event_type == 'llm_call_end':
            task_type = entry.get('task_type')
            if task_type == 'generation':
                sessions[session_id]['generation'].append(entry)
        
        # Track errors
        if 'error' in entry or 'exception' in str(entry).lower():
            sessions[session_id]['errors'].append(entry)
    
    # Find sessions with merge_step but no generation
    missing_gen_sessions = []
    
    for session_id, data in sessions.items():
        merge_count = len(data['merge_step'])
        gen_count = len(data['generation'])
        
        if merge_count > 0 and gen_count == 0:
            missing_gen_sessions.append((session_id, data))
    
    print(f"Total sessions: {len(sessions)}")
    print(f"Sessions with merge_step: {sum(1 for s in sessions.values() if s['merge_step'])}")
    print(f"Sessions with generation: {sum(1 for s in sessions.values() if s['generation'])}")
    print(f"Sessions with merge_step but NO generation: {len(missing_gen_sessions)}")
    print()
    
    if missing_gen_sessions:
        print("=" * 80)
        print("SESSIONS WITH MISSING GENERATION")
        print("=" * 80)
        print()
        
        for i, (session_id, data) in enumerate(missing_gen_sessions[:10], 1):
            print(f"\n{i}. Session: {session_id}")
            print(f"   Merge steps: {len(data['merge_step'])}")
            print(f"   Generations: {len(data['generation'])}")
            print(f"   Errors: {len(data['errors'])}")
            
            # Check for errors
            if data['errors']:
                print(f"   ⚠️  Has errors:")
                for error in data['errors'][:3]:
                    error_msg = error.get('message') or str(error).get('error', 'Unknown error')
                    print(f"      - {error_msg[:100]}")
            
            # Check event sequence
            print(f"   Event sequence:")
            for event in data['all_events'][:10]:
                event_type = event.get('type')
                step_name = event.get('step_name', '')
                task_type = event.get('task_type', '')
                
                if event_type == 'step_start':
                    print(f"      → step_start: {step_name}")
                elif event_type == 'step_end':
                    print(f"      ← step_end: {step_name}")
                elif event_type == 'llm_call_start':
                    print(f"      → llm_call_start: {task_type}")
                elif event_type == 'llm_call_end':
                    print(f"      ← llm_call_end: {task_type}")
                elif 'error' in event_type.lower():
                    print(f"      ✗ {event_type}")
            
            if len(data['all_events']) > 10:
                print(f"      ... and {len(data['all_events']) - 10} more events")
        
        if len(missing_gen_sessions) > 10:
            print(f"\n... and {len(missing_gen_sessions) - 10} more sessions")
        print()
    
    # Analyze patterns
    print("=" * 80)
    print("PATTERN ANALYSIS")
    print("=" * 80)
    print()
    
    # Count sessions by merge_step:generation ratio
    ratio_counts = defaultdict(int)
    
    for session_id, data in sessions.items():
        merge_count = len(data['merge_step'])
        gen_count = len(data['generation'])
        
        if merge_count > 0:
            if gen_count == 0:
                ratio = "N:0 (missing)"
            elif merge_count == gen_count:
                ratio = "1:1 (normal)"
            elif gen_count > merge_count:
                ratio = f"1:{gen_count/merge_count:.1f} (more gen)"
            else:
                ratio = f"{merge_count/gen_count:.1f}:1 (more merge)"
            
            ratio_counts[ratio] += 1
    
    print("Session patterns:")
    print("-" * 80)
    for ratio in sorted(ratio_counts.keys()):
        count = ratio_counts[ratio]
        bar = "█" * min(count, 50)
        print(f"  {ratio:<20} {count:>3} sessions {bar}")
    print()
    
    # Check for common error patterns
    error_patterns = defaultdict(int)
    
    for session_id, data in missing_gen_sessions:
        if data['errors']:
            for error in data['errors']:
                error_type = error.get('type', 'unknown')
                error_msg = str(error.get('message', ''))[:50]
                error_patterns[f"{error_type}: {error_msg}"] += 1
        else:
            error_patterns["No error recorded"] += 1
    
    if error_patterns:
        print("Common error patterns in missing generation sessions:")
        print("-" * 80)
        for pattern in sorted(error_patterns.keys(), key=lambda x: error_patterns[x], reverse=True)[:10]:
            count = error_patterns[pattern]
            print(f"  {count:>3}x {pattern}")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    total_merge = sum(len(s['merge_step']) for s in sessions.values())
    total_gen = sum(len(s['generation']) for s in sessions.values())
    missing_count = total_merge - total_gen
    
    print(f"Total merge_step calls: {total_merge}")
    print(f"Total generation calls: {total_gen}")
    print(f"Missing generations: {missing_count}")
    print(f"Missing rate: {missing_count/total_merge*100:.1f}%")
    print()
    
    if missing_count > 0:
        print("⚠️  Some merge_step calls did not result in generation calls")
        print()
        print("Possible reasons:")
        print("  1. Errors occurred after merge_step")
        print("  2. Request was cancelled/timed out")
        print("  3. Generation was skipped due to business logic")
        print("  4. Test scenarios that only test merge_step")
        print()
        print("Recommendations:")
        print("  - Check the 'SESSIONS WITH MISSING GENERATION' section above")
        print("  - Review error logs for those sessions")
        print("  - Check if this is expected behavior for your test scenarios")
    else:
        print("✓ All merge_step calls have corresponding generation calls")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python find_missing_generations.py <trace_file>")
        print()
        print("Example:")
        print("  python find_missing_generations.py logs/trace.jsonl")
        sys.exit(1)
    
    trace_file = sys.argv[1]
    
    if not Path(trace_file).exists():
        print(f"Error: Trace file not found: {trace_file}")
        sys.exit(1)
    
    find_missing_generations(trace_file)


if __name__ == "__main__":
    main()
