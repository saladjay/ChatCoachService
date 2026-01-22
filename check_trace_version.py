"""Check if prompt_version is in trace file."""
import json

with open('logs/trace.jsonl', 'r', encoding='utf-8') as f:
    lines = [json.loads(l) for l in f if 'test_user_phase3' in l]

print(f"Found {len(lines)} entries with test_user_phase3")
print("\nLast 4 entries:")
for entry in lines[-4:]:
    entry_type = entry.get('type')
    prompt_version = entry.get('prompt_version')
    task_type = entry.get('task_type')
    print(f"  {entry_type} ({task_type}): prompt_version={prompt_version}")
