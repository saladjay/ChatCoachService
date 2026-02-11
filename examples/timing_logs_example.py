"""
Example: Using Timing Logs for Performance Monitoring

This example demonstrates how to enable and use timing logs to monitor
the performance of the ChatCoach API.
"""

import os
import json
from pathlib import Path

# Step 1: Enable timing logs via environment variables
os.environ["TRACE_ENABLED"] = "true"
os.environ["TRACE_LEVEL"] = "debug"
os.environ["TRACE_LOG_TIMING"] = "true"
os.environ["TRACE_FILE_PATH"] = "logs/trace.jsonl"

print("Timing logs configuration:")
print(f"  TRACE_ENABLED: {os.getenv('TRACE_ENABLED')}")
print(f"  TRACE_LEVEL: {os.getenv('TRACE_LEVEL')}")
print(f"  TRACE_LOG_TIMING: {os.getenv('TRACE_LOG_TIMING')}")
print(f"  TRACE_FILE_PATH: {os.getenv('TRACE_FILE_PATH')}")
print()

# Step 2: Make API requests (timing logs will be automatically recorded)
print("Make API requests to generate timing logs...")
print("Example: POST /api/v1/ChatCoach/predict")
print()

# Step 3: Analyze timing logs
def analyze_timing_logs(log_file: str = "logs/trace.jsonl"):
    """Analyze timing logs to identify performance bottlenecks."""
    
    if not Path(log_file).exists():
        print(f"Log file not found: {log_file}")
        return
    
    print(f"Analyzing timing logs from: {log_file}")
    print("-" * 80)
    
    # Collect timing data by type
    timing_data = {}
    
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                event = json.loads(line)
                
                # Only process timing events
                if event.get("level") == "debug" and "duration_ms" in event:
                    event_type = event.get("type", "unknown")
                    duration = event.get("duration_ms", 0)
                    
                    if event_type not in timing_data:
                        timing_data[event_type] = []
                    
                    timing_data[event_type].append(duration)
            
            except json.JSONDecodeError:
                continue
    
    # Print statistics
    if not timing_data:
        print("No timing data found in logs")
        return
    
    print("\nTiming Statistics:")
    print(f"{'Event Type':<30} {'Count':<10} {'Avg (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12}")
    print("-" * 80)
    
    for event_type, durations in sorted(timing_data.items()):
        count = len(durations)
        avg = sum(durations) / count
        min_dur = min(durations)
        max_dur = max(durations)
        
        print(f"{event_type:<30} {count:<10} {avg:<12.2f} {min_dur:<12} {max_dur:<12}")
    
    print("-" * 80)
    
    # Identify bottlenecks (operations taking >1000ms on average)
    print("\nPerformance Bottlenecks (avg > 1000ms):")
    bottlenecks = [(k, sum(v)/len(v)) for k, v in timing_data.items() if sum(v)/len(v) > 1000]
    
    if bottlenecks:
        for event_type, avg_duration in sorted(bottlenecks, key=lambda x: x[1], reverse=True):
            print(f"  - {event_type}: {avg_duration:.2f}ms")
    else:
        print("  No bottlenecks detected")
    
    print()


# Example usage
if __name__ == "__main__":
    print("=" * 80)
    print("Timing Logs Example")
    print("=" * 80)
    print()
    
    # Analyze existing logs
    analyze_timing_logs()
    
    print("\nTo generate timing logs:")
    print("1. Set environment variables as shown above")
    print("2. Start the server: python main.py")
    print("3. Make API requests")
    print("4. Run this script to analyze: python examples/timing_logs_example.py")
    print()
    
    print("To view raw timing logs:")
    print("  cat logs/trace.jsonl | grep duration_ms")
    print()
    
    print("To find slow operations:")
    print("  cat logs/trace.jsonl | jq 'select(.duration_ms > 1000)'")
    print()
