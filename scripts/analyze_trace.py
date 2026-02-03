"""
Trace File Analyzer

Analyzes trace.jsonl files to extract and display token usage information.

Usage:
    python scripts/analyze_trace.py logs/trace.jsonl
    python scripts/analyze_trace.py logs/trace_baseline.jsonl logs/trace_optimized.jsonl --compare
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Dict


def load_trace_file(filepath: str) -> List[Dict]:
    """Load and parse trace.jsonl file.
    
    Args:
        filepath: Path to trace file
    
    Returns:
        List of trace entries
    """
    if not Path(filepath).exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse line {line_num}: {e}")
    
    return entries


def extract_llm_calls(entries: List[Dict]) -> List[Dict]:
    """Extract LLM call entries from trace.
    
    Args:
        entries: List of trace entries
    
    Returns:
        List of LLM call entries
    """
    llm_calls = []
    prompts_by_call_id = {}
    versions_by_call_id = {}
    callers_by_call_id = {}
    
    # First pass: collect prompts and versions from llm_call_start events
    for entry in entries:
        if entry.get("type") == "llm_call_start":
            call_id = entry.get("call_id")
            if call_id:
                prompts_by_call_id[call_id] = entry.get("prompt", "")
                versions_by_call_id[call_id] = entry.get("prompt_version")
                callers_by_call_id[call_id] = {
                    "caller_module": entry.get("caller_module"),
                    "caller_func": entry.get("caller_func"),
                }
    
    # Second pass: collect results from llm_call_end events
    for entry in entries:
        if entry.get("type") == "llm_call_end":
            call_id = entry.get("call_id")
            prompt = prompts_by_call_id.get(call_id, "")
            prompt_version = versions_by_call_id.get(call_id) or entry.get("prompt_version")
            caller_info = callers_by_call_id.get(call_id) or {}
            caller_module = entry.get("caller_module") or caller_info.get("caller_module")
            caller_func = entry.get("caller_func") or caller_info.get("caller_func")
            
            llm_calls.append({
                "timestamp": entry.get("ts"),
                "task_type": entry.get("task_type"),
                "provider": entry.get("provider"),
                "model": entry.get("model"),
                "input_tokens": entry.get("input_tokens", 0),
                "output_tokens": entry.get("output_tokens", 0),
                "total_tokens": entry.get("input_tokens", 0) + entry.get("output_tokens", 0),
                "cost_usd": entry.get("cost_usd", 0),
                "latency_ms": entry.get("duration_ms", 0),
                "prompt": prompt,
                "prompt_version": prompt_version,
                "caller_module": caller_module,
                "caller_func": caller_func,
                "response": entry.get("text", "")
            })
    
    return llm_calls


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return float(min(values))
    if p >= 100:
        return float(max(values))
    ordered = sorted(values)
    k = (len(ordered) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return float(ordered[f])
    d0 = ordered[f] * (c - k)
    d1 = ordered[c] * (k - f)
    return float(d0 + d1)


def print_latency_summary(llm_calls: List[Dict], group_key: str = "task_type"):
    grouped: dict[str, List[float]] = defaultdict(list)
    for call in llm_calls:
        latency = call.get("latency_ms") or 0
        if latency <= 0:
            continue
        k = call.get(group_key) or "unknown"
        grouped[str(k)].append(float(latency))

    if not grouped:
        return

    rows = []
    for k, latencies in grouped.items():
        rows.append(
            {
                "key": k,
                "count": len(latencies),
                "mean": sum(latencies) / len(latencies),
                "p50": _percentile(latencies, 50),
                "p90": _percentile(latencies, 90),
                "min": min(latencies),
                "max": max(latencies),
            }
        )

    rows.sort(key=lambda r: (-(r["mean"] or 0), r["key"]))

    print(f"\nLATENCY SUMMARY BY {group_key.upper()}")
    print("-" * 80)
    print(f"{'Type':<28} {'N':>6} {'Mean(ms)':>10} {'P50':>10} {'P90':>10} {'Min':>10} {'Max':>10}")
    print("-" * 80)
    for r in rows:
        print(
            f"{r['key'][:28]:<28}"
            f" {r['count']:>6}"
            f" {r['mean']:>10.0f}"
            f" {r['p50']:>10.0f}"
            f" {r['p90']:>10.0f}"
            f" {r['min']:>10.0f}"
            f" {r['max']:>10.0f}"
        )


def print_summary(llm_calls: List[Dict], title: str = "TRACE ANALYSIS", latency_group: str = "task_type"):
    """Print summary of LLM calls.
    
    Args:
        llm_calls: List of LLM call entries
        title: Title for the summary
        latency_group: Group key for latency aggregation
    """
    print("\n" + "="*80)
    print(title)
    print("="*80)
    
    if not llm_calls:
        print("\nNo LLM calls found in trace file")
        return
    
    total_input = sum(call["input_tokens"] for call in llm_calls)
    total_output = sum(call["output_tokens"] for call in llm_calls)
    total_tokens = total_input + total_output
    total_cost = sum(call["cost_usd"] for call in llm_calls)
    avg_latency = sum(call["latency_ms"] for call in llm_calls) / len(llm_calls)
    
    print(f"\nOVERALL STATISTICS")
    print("-" * 80)
    print(f"  Total LLM Calls:    {len(llm_calls)}")
    print(f"  Total Input Tokens: {total_input:,}")
    print(f"  Total Output Tokens: {total_output:,}")
    print(f"  Total Tokens:       {total_tokens:,}")
    print(f"  Total Cost:         ${total_cost:.6f}")
    print(f"  Average Latency:    {avg_latency:.0f}ms")
    
    print(f"\nCALL BREAKDOWN")
    print("-" * 80)
    print(f"{'#':<4} {'Task Type':<20} {'Model':<20} {'In':<8} {'Out':<8} {'Total':<8} {'Cost':<12}")
    print("-" * 80)
    
    for i, call in enumerate(llm_calls, 1):
        print(f"{i:<4} {call['task_type']:<20} {call['model']:<20} "
              f"{call['input_tokens']:<8} {call['output_tokens']:<8} "
              f"{call['total_tokens']:<8} ${call['cost_usd']:<11.6f}")

    print_latency_summary(llm_calls, group_key=latency_group)


def print_detailed_call(call: Dict, call_num: int):
    """Print detailed information about a single call.
    
    Args:
        call: LLM call entry
        call_num: Call number
    """
    print(f"\n{'='*80}")
    print(f"CALL #{call_num}: {call['task_type'].upper()}")
    print(f"{'='*80}")
    
    print(f"\nMetadata:")
    print(f"  Timestamp: {call['timestamp']}")
    print(f"  Provider:  {call['provider']}")
    print(f"  Model:     {call['model']}")
    print(f"  Latency:   {call['latency_ms']}ms")
    
    # Display prompt version if available
    if call.get('prompt_version'):
        print(f"  Prompt Version: {call['prompt_version']}")
    
    print(f"\nToken Usage:")
    print(f"  Input:  {call['input_tokens']:>6} tokens")
    print(f"  Output: {call['output_tokens']:>6} tokens")
    print(f"  Total:  {call['total_tokens']:>6} tokens")
    print(f"  Cost:   ${call['cost_usd']:.6f}")
    
    print(f"\nPrompt ({len(call['prompt'])} characters):")
    print("-" * 80)
    if len(call['prompt']) > 2000:
        print(call['prompt'][:1000])
        print(f"\n... [truncated {len(call['prompt']) - 2000} characters] ...\n")
        print(call['prompt'][-1000:])
    else:
        print(call['prompt'])
    
    print(f"\nResponse ({len(call['response'])} characters):")
    print("-" * 80)
    if len(call['response']) > 2000:
        print(call['response'][:1000])
        print(f"\n... [truncated {len(call['response']) - 2000} characters] ...\n")
        print(call['response'][-1000:])
    else:
        print(call['response'])


def compare_traces(baseline_calls: List[Dict], optimized_calls: List[Dict]):
    """Compare two trace files.
    
    Args:
        baseline_calls: LLM calls from baseline trace
        optimized_calls: LLM calls from optimized trace
    """
    print("\n" + "="*80)
    print("COMPARISON REPORT")
    print("="*80)
    
    baseline_total = sum(call["total_tokens"] for call in baseline_calls)
    optimized_total = sum(call["total_tokens"] for call in optimized_calls)
    
    baseline_input = sum(call["input_tokens"] for call in baseline_calls)
    optimized_input = sum(call["input_tokens"] for call in optimized_calls)
    
    baseline_output = sum(call["output_tokens"] for call in baseline_calls)
    optimized_output = sum(call["output_tokens"] for call in optimized_calls)
    
    baseline_cost = sum(call["cost_usd"] for call in baseline_calls)
    optimized_cost = sum(call["cost_usd"] for call in optimized_calls)
    
    print(f"\nOVERALL COMPARISON")
    print("-" * 80)
    print(f"{'Metric':<25} {'Baseline':<15} {'Optimized':<15} {'Change':<15}")
    print("-" * 80)
    
    # Total tokens
    if baseline_total > 0:
        total_change = ((baseline_total - optimized_total) / baseline_total) * 100
    else:
        total_change = 0
    print(f"{'Total Tokens':<25} {baseline_total:<15,} {optimized_total:<15,} {total_change:>+.1f}%")
    
    # Input tokens
    if baseline_input > 0:
        input_change = ((baseline_input - optimized_input) / baseline_input) * 100
    else:
        input_change = 0
    print(f"{'Input Tokens':<25} {baseline_input:<15,} {optimized_input:<15,} {input_change:>+.1f}%")
    
    # Output tokens
    if baseline_output > 0:
        output_change = ((baseline_output - optimized_output) / baseline_output) * 100
    else:
        output_change = 0
    print(f"{'Output Tokens':<25} {baseline_output:<15,} {optimized_output:<15,} {output_change:>+.1f}%")
    
    # Cost
    if baseline_cost > 0:
        cost_change = ((baseline_cost - optimized_cost) / baseline_cost) * 100
    else:
        cost_change = 0
    print(f"{'Total Cost (USD)':<25} ${baseline_cost:<14.6f} ${optimized_cost:<14.6f} {cost_change:>+.1f}%")
    
    # Number of calls
    print(f"{'Number of Calls':<25} {len(baseline_calls):<15} {len(optimized_calls):<15}")
    
    # Per-call comparison
    print(f"\nPER-CALL COMPARISON")
    print("-" * 80)
    
    max_calls = max(len(baseline_calls), len(optimized_calls))
    
    for i in range(max_calls):
        if i < len(baseline_calls) and i < len(optimized_calls):
            b_call = baseline_calls[i]
            o_call = optimized_calls[i]
            
            print(f"\nCall #{i+1}: {b_call['task_type']}")
            print(f"  Model: {b_call['model']}")
            
            if b_call['input_tokens'] > 0:
                input_pct = ((b_call['input_tokens'] - o_call['input_tokens']) / b_call['input_tokens']) * 100
            else:
                input_pct = 0
            print(f"  Input:  {b_call['input_tokens']:>6} → {o_call['input_tokens']:>6} ({input_pct:>+.1f}%)")
            
            if b_call['output_tokens'] > 0:
                output_pct = ((b_call['output_tokens'] - o_call['output_tokens']) / b_call['output_tokens']) * 100
            else:
                output_pct = 0
            print(f"  Output: {b_call['output_tokens']:>6} → {o_call['output_tokens']:>6} ({output_pct:>+.1f}%)")
            
            if b_call['total_tokens'] > 0:
                total_pct = ((b_call['total_tokens'] - o_call['total_tokens']) / b_call['total_tokens']) * 100
            else:
                total_pct = 0
            print(f"  Total:  {b_call['total_tokens']:>6} → {o_call['total_tokens']:>6} ({total_pct:>+.1f}%)")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Analyze trace.jsonl files to extract token usage information"
    )
    parser.add_argument(
        "trace_files",
        nargs="+",
        help="Path to trace.jsonl file(s)"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare two trace files (requires exactly 2 files)"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed information for each LLM call"
    )
    parser.add_argument(
        "--latency-group",
        default="task_type",
        choices=["task_type", "caller_module", "prompt_version", "provider", "model"],
        help="Group key for latency aggregation (default: task_type)"
    )
    
    args = parser.parse_args()
    
    if args.compare:
        if len(args.trace_files) != 2:
            print("Error: --compare requires exactly 2 trace files")
            sys.exit(1)
        
        # Load both files
        print(f"📂 Loading baseline trace: {args.trace_files[0]}")
        baseline_entries = load_trace_file(args.trace_files[0])
        baseline_calls = extract_llm_calls(baseline_entries)
        
        print(f"📂 Loading optimized trace: {args.trace_files[1]}")
        optimized_entries = load_trace_file(args.trace_files[1])
        optimized_calls = extract_llm_calls(optimized_entries)
        
        # Print summaries
        print_summary(baseline_calls, "BASELINE TRACE ANALYSIS", latency_group=args.latency_group)
        print_summary(optimized_calls, "OPTIMIZED TRACE ANALYSIS", latency_group=args.latency_group)
        
        # Compare
        compare_traces(baseline_calls, optimized_calls)
        
        # Detailed view if requested
        if args.detailed:
            print("\n" + "="*80)
            print("DETAILED BASELINE CALLS")
            print("="*80)
            for i, call in enumerate(baseline_calls, 1):
                print_detailed_call(call, i)
            
            print("\n" + "="*80)
            print("DETAILED OPTIMIZED CALLS")
            print("="*80)
            for i, call in enumerate(optimized_calls, 1):
                print_detailed_call(call, i)
    
    else:
        # Analyze single file(s)
        for trace_file in args.trace_files:
            print(f"\nLoading trace: {trace_file}")
            entries = load_trace_file(trace_file)
            llm_calls = extract_llm_calls(entries)
            
            print_summary(llm_calls, f"TRACE ANALYSIS: {trace_file}", latency_group=args.latency_group)
            
            if args.detailed:
                for i, call in enumerate(llm_calls, 1):
                    print_detailed_call(call, i)


if __name__ == "__main__":
    main()
