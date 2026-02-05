#!/usr/bin/env python3
"""Analyze failed JSON reply logs to identify patterns."""

import json
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

def analyze_failed_logs(log_dir: Path = Path("logs/failed_json_replies")):
    """Analyze failed JSON logs and print statistics."""
    
    if not log_dir.exists():
        print(f"❌ Log directory not found: {log_dir}")
        print("   Enable LOG_FAILED_JSON_REPLIES=true and run tests to generate logs")
        return
    
    log_files = list(log_dir.glob("*.json"))
    
    if not log_files:
        print(f"✓ No failed JSON logs found in {log_dir}")
        print("  This is good! All JSON parsing succeeded.")
        return
    
    print("=" * 80)
    print(f"Failed JSON Reply Analysis")
    print("=" * 80)
    print()
    print(f"Log directory: {log_dir.absolute()}")
    print(f"Total failures: {len(log_files)}")
    print()
    
    # Load all logs
    logs = []
    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs.append(json.load(f))
        except Exception as e:
            print(f"⚠️  Failed to read {log_file.name}: {e}")
    
    if not logs:
        print("❌ No valid log files found")
        return
    
    # Analyze error types
    print("=" * 80)
    print("Error Types")
    print("=" * 80)
    error_types = Counter(log['error'] for log in logs)
    for error, count in error_types.most_common():
        percentage = count / len(logs) * 100
        print(f"{count:3d} ({percentage:5.1f}%) - {error[:70]}")
    print()
    
    # Analyze reply lengths
    print("=" * 80)
    print("Reply Length Statistics")
    print("=" * 80)
    lengths = [log['reply_length'] for log in logs]
    print(f"Min:    {min(lengths):6d} chars")
    print(f"Max:    {max(lengths):6d} chars")
    print(f"Mean:   {sum(lengths) / len(lengths):6.0f} chars")
    print(f"Median: {sorted(lengths)[len(lengths) // 2]:6d} chars")
    print()
    
    # Show sample failures
    print("=" * 80)
    print("Sample Failures (first 3)")
    print("=" * 80)
    for i, log in enumerate(logs[:3], 1):
        print(f"\n--- Sample {i} ---")
        print(f"Timestamp:  {log['timestamp']}")
        print(f"Session ID: {log['session_id'][:16]}...")
        print(f"Error:      {log['error']}")
        print(f"Reply text (first 200 chars):")
        print(f"  {log['reply_text'][:200]}")
        if len(log['reply_text']) > 200:
            print(f"  ... ({len(log['reply_text']) - 200} more chars)")
    print()
    
    # Common patterns
    print("=" * 80)
    print("Common Patterns")
    print("=" * 80)
    
    # Check for markdown code blocks
    markdown_count = sum(1 for log in logs if '```' in log['reply_text'])
    print(f"Contains markdown code blocks (```): {markdown_count}/{len(logs)} ({markdown_count/len(logs)*100:.1f}%)")
    
    # Check for missing quotes
    missing_quotes = sum(1 for log in logs if 'property name' in log['error'].lower())
    print(f"Missing quotes around keys:          {missing_quotes}/{len(logs)} ({missing_quotes/len(logs)*100:.1f}%)")
    
    # Check for incomplete JSON
    incomplete = sum(1 for log in logs if 'unterminated' in log['error'].lower() or 'expecting' in log['error'].lower())
    print(f"Incomplete/malformed JSON:           {incomplete}/{len(logs)} ({incomplete/len(logs)*100:.1f}%)")
    
    # Check for extra text
    extra_text = sum(1 for log in logs if 'extra data' in log['error'].lower())
    print(f"Extra text after JSON:               {extra_text}/{len(logs)} ({extra_text/len(logs)*100:.1f}%)")
    print()
    
    # Recommendations
    print("=" * 80)
    print("Recommendations")
    print("=" * 80)
    
    if markdown_count > len(logs) * 0.5:
        print("✓ Most failures contain markdown - parse_json_with_markdown() should handle this")
    
    if missing_quotes > len(logs) * 0.3:
        print("⚠️  Many failures due to missing quotes - consider updating prompt:")
        print("   'Output ONLY valid JSON with double quotes around all keys'")
    
    if incomplete > len(logs) * 0.3:
        print("⚠️  Many incomplete JSON responses - consider:")
        print("   - Increasing max_tokens limit")
        print("   - Simplifying output schema")
        print("   - Adding 'Complete the JSON object' instruction")
    
    if extra_text > len(logs) * 0.2:
        print("⚠️  Extra text after JSON - consider:")
        print("   - Stricter prompt: 'Output ONLY JSON, no explanations'")
        print("   - Better JSON extraction in parse_json_with_markdown()")
    
    print()
    print("=" * 80)
    print(f"Analysis complete. Review logs in: {log_dir.absolute()}")
    print("=" * 80)


if __name__ == "__main__":
    log_dir = Path("logs/failed_json_replies")
    if len(sys.argv) > 1:
        log_dir = Path(sys.argv[1])
    
    analyze_failed_logs(log_dir)
