"""
Quick script to compare baseline vs optimized runs from phase3 example.
"""
import json

trace_file = "logs/trace.jsonl"

baseline_calls = []
optimized_calls = []

with open(trace_file, 'r', encoding='utf-8') as f:
    for line in f:
        entry = json.loads(line)
        if entry.get("type") == "llm_call_end":
            user_id = entry.get("user_id", "")
            if "test_user_phase3_baseline" in user_id:
                baseline_calls.append(entry)
            elif "test_user_phase3_optimized" in user_id:
                optimized_calls.append(entry)

baseline_total = sum(c.get("input_tokens", 0) + c.get("output_tokens", 0) for c in baseline_calls)
baseline_input = sum(c.get("input_tokens", 0) for c in baseline_calls)
baseline_output = sum(c.get("output_tokens", 0) for c in baseline_calls)

optimized_total = sum(c.get("input_tokens", 0) + c.get("output_tokens", 0) for c in optimized_calls)
optimized_input = sum(c.get("input_tokens", 0) for c in optimized_calls)
optimized_output = sum(c.get("output_tokens", 0) for c in optimized_calls)

print("="*80)
print("PHASE 3 BASELINE VS OPTIMIZED COMPARISON")
print("="*80)
print(f"\nBaseline:  {baseline_total:>5} tokens ({baseline_input:>4} input + {baseline_output:>4} output) - {len(baseline_calls)} calls")
print(f"Optimized: {optimized_total:>5} tokens ({optimized_input:>4} input + {optimized_output:>4} output) - {len(optimized_calls)} calls")

if baseline_total > 0:
    reduction = ((baseline_total - optimized_total) / baseline_total) * 100
    print(f"\nReduction: {reduction:>5.1f}% ({baseline_total - optimized_total} tokens saved)")
